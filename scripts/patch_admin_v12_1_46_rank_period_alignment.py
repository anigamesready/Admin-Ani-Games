from pathlib import Path
p = Path('android/app/src/main/assets/web/admin.html')
if not p.is_file():
    raise SystemExit('Admin report asset missing.')
s = p.read_text(encoding='utf-8')
marker = 'V12.1.46-MONTHLY-YEARLY-PC-REPORT-EXPORT'
if marker not in s:
    raise SystemExit('V12.1.46 report patch must run first.')
old = r'''async function loadMonthlyPcReportExport(){
 if(!currentOrg?.id)throw new Error('Workspace belum dipilih untuk laporan bulanan/per-PC.');
 const fromDay=$('from')?.value,toDay=$('to')?.value;
 if(!fromDay||!toDay)throw new Error('Pilih tanggal awal dan akhir laporan.');
 const mainRange=reportRangeForDays(fromDay,toDay),firstMonth=reportMonthKey(fromDay)+'-01';
 const previousMonthStart=reportShiftJakartaDay(firstMonth,-1).slice(0,7)+'-01';
 const expandedRange=reportRangeForDays(previousMonthStart,toDay);
 const priorFrom=reportShiftJakartaDay(fromDay,-12),priorTo=reportShiftJakartaDay(toDay,-12);
 const priorYearRange=reportRangeForDays(priorFrom,priorTo);
 const args=range=>({p_org_id:currentOrg.id,p_from:range.from,p_to:range.to});
 const [current,previousYear]=await Promise.all([
  rpc('report_rental_period_breakdown',args(expandedRange)),
  rpc('report_rental_period_breakdown',args(priorYearRange))
 ]);
 if(!current||!Array.isArray(current.combined_rows)||!Array.isArray(current.pc_rows))throw new Error('Server tidak mengembalikan rekap gabungan dan rekap PC yang lengkap.');
 if(!previousYear||!Array.isArray(previousYear.combined_rows)||!Array.isArray(previousYear.pc_rows))throw new Error('Rekap pembanding tahun lalu tidak lengkap.');
 const monthKeys=reportMonthKeys(fromDay,toDay),selected=new Set(monthKeys);
 return {monthKeys,combinedRows:current.combined_rows.filter(x=>selected.has(x.month)),pcRows:current.pc_rows.filter(x=>selected.has(x.month)),
  priorMonthRows:current.combined_rows.filter(x=>!selected.has(x.month)),priorMonthPcRows:current.pc_rows.filter(x=>!selected.has(x.month)),
  previousYearRows:previousYear.combined_rows,previousYearPcRows:previousYear.pc_rows,mainRange,priorYearRange};
}'''
new = r'''async function loadMonthlyPcReportExport(){
 if(!currentOrg?.id)throw new Error('Workspace belum dipilih untuk laporan bulanan/per-PC.');
 const fromDay=$('from')?.value,toDay=$('to')?.value;
 if(!fromDay||!toDay)throw new Error('Pilih tanggal awal dan akhir laporan.');
 const mainRange=reportRangeForDays(fromDay,toDay);
 const prevMonthRange=reportRangeForDays(reportShiftJakartaDay(fromDay,-1),reportShiftJakartaDay(toDay,-1));
 const priorYearRange=reportRangeForDays(reportShiftJakartaDay(fromDay,-12),reportShiftJakartaDay(toDay,-12));
 const args=range=>({p_org_id:currentOrg.id,p_from:range.from,p_to:range.to});
 const [current,previousMonth,previousYear]=await Promise.all([
  rpc('report_rental_period_breakdown',args(mainRange)),
  rpc('report_rental_period_breakdown',args(prevMonthRange)),
  rpc('report_rental_period_breakdown',args(priorYearRange))
 ]);
 for(const [label,data] of [['periode berjalan',current],['pembanding bulan lalu',previousMonth],['pembanding tahun lalu',previousYear]]){
  if(!data||!Array.isArray(data.combined_rows)||!Array.isArray(data.pc_rows))throw new Error('Server tidak mengembalikan rekap gabungan/per-PC untuk '+label+'.');
 }
 const monthKeys=reportMonthKeys(fromDay,toDay),selected=new Set(monthKeys);
 return {monthKeys,combinedRows:current.combined_rows.filter(x=>selected.has(x.month)),pcRows:current.pc_rows.filter(x=>selected.has(x.month)),
  priorMonthRows:previousMonth.combined_rows,priorMonthPcRows:previousMonth.pc_rows,
  previousYearRows:previousYear.combined_rows,previousYearPcRows:previousYear.pc_rows,mainRange,prevMonthRange,priorYearRange};
}'''
if s.count(old) == 0:
    if "const prevMonthRange=reportRangeForDays(reportShiftJakartaDay(fromDay,-1),reportShiftJakartaDay(toDay,-1));" in s:
        print('PASS: period alignment already applied')
        raise SystemExit(0)
    raise SystemExit('Original monthly comparison helper not found; refusing unsafe edit.')
if s.count(old) != 1:
    raise SystemExit(f'Expected exactly one monthly comparison helper, found {s.count(old)}')
s = s.replace(old, new, 1)
checks = [
    "const prevMonthRange=reportRangeForDays(reportShiftJakartaDay(fromDay,-1),reportShiftJakartaDay(toDay,-1));",
    "const [current,previousMonth,previousYear]=await Promise.all([",
    "priorMonthRows:previousMonth.combined_rows,priorMonthPcRows:previousMonth.pc_rows",
]
for item in checks:
    if item not in s:
        raise SystemExit('Alignment regression check missing: '+item)
p.write_text(s, encoding='utf-8')
print('PASS: month-to-month ranking compares equivalent date windows (shift by one month); year comparison shifts by 12 months.')
