from pathlib import Path
import re

PAGE=Path("android/app/src/main/assets/web/admin.html")
GRADLE=Path("android/app/build.gradle")
MANIFEST=Path("android/app/src/main/AndroidManifest.xml")
VERSION=Path("VERSION.txt")
MARKER="V12.1.51-BILLING-STOP-PAUSE-POLICY"
page=PAGE.read_text(encoding="utf-8")
gradle=GRADLE.read_text(encoding="utf-8")
manifest=MANIFEST.read_text(encoding="utf-8")
if MARKER in page:
    print("PASS: Admin V12.1.51 Stop/Pause policy already applied")
    raise SystemExit(0)

old="ANI-WOL-RELAY V12.1.50"
if page.count(old)!=1: raise SystemExit("Admin relay marker anchor mismatch")
page=page.replace(old,"ANI-WOL-RELAY V12.1.51",1)

nav='<button id="freeTestPolicyNav" onclick="openFreeTestPolicyMenu()">🛂 FREE TEST 10 MENIT</button>'
if page.count(nav)!=1: raise SystemExit("FREE TEST navigation anchor mismatch")
page=page.replace(nav,nav+'<button id="billingStopPausePolicyNav" onclick="openBillingStopPausePolicyMenu()">🔐 PAUSE / STOP BILLING</button>',1)

wake='<div class="card" id="wakeRelayCard"'
if page.count(wake)!=1: raise SystemExit("WoL card anchor mismatch")
card="""<div class="card" id="billingStopPausePolicyCard" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top"><div><h3 style="margin:0">🔐 Izin PAUSE / STOP BILLING</h3><div class="muted">Master/Owner menentukan apakah penyewa boleh memakai PAUSE / STOP atau tombol X pada timer PC.</div></div><span id="billingStopPausePolicyState" class="pill">BELUM DIPERIKSA</span></div>
 <div class="msg" style="margin-top:10px">Jika OFF, akses PAUSE / STOP penyewa dikunci dan timer tetap berjalan. Kontrol Admin serta akhir waktu otomatis tetap berfungsi.</div>
 <label class="row" style="display:flex;align-items:center;gap:10px;margin-top:12px"><input id="billingStopPausePolicySwitch" type="checkbox" disabled><span>Izinkan penyewa menggunakan PAUSE / STOP</span></label>
 <div class="row" style="margin-top:10px"><button type="button" onclick="loadBillingStopPausePolicy()">Muat Status</button><button id="billingStopPausePolicySave" type="button" class="primary" onclick="saveBillingStopPausePolicy()" disabled>Simpan Pengaturan</button></div>
 <div id="billingStopPausePolicyMessage" class="msg" role="status" aria-live="polite" style="margin-top:10px">Status awal OFF. Muat status dari database untuk mengubah izin.</div>
</div>

"""
page=page.replace(wake,card+wake,1)

role="const freeTestCard=$('freeTestPolicyCard');if(freeTestCard)freeTestCard.classList.toggle('hidden',!owner);"
if page.count(role)!=1: raise SystemExit("Owner visibility anchor mismatch")
page=page.replace(role,role+"const stopPauseNav=$('billingStopPausePolicyNav');if(stopPauseNav)stopPauseNav.classList.toggle('hidden',!owner);const stopPauseCard=$('billingStopPausePolicyCard');if(stopPauseCard)stopPauseCard.classList.toggle('hidden',!owner);",1)

anchor=re.search(r"const LOCAL_API_KEY\s*=\s*'ani_games_ready_db_android_api_url_v1';",page)
if not anchor: raise SystemExit("Admin JS insertion anchor mismatch")
functions=r"""
// V12.1.51-BILLING-STOP-PAUSE-POLICY — Owner-only DB-backed policy.
function billingStopPausePolicyIsOwner(){const role=String(ctx?.role||'').trim().toLowerCase();return role==='owner'||role==='super_admin';}
function openBillingStopPausePolicyMenu(){
 try{if(typeof closeMobileNav==='function')closeMobileNav();}catch(_){}
 tab('devices');
 document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));
 const btn=$('billingStopPausePolicyNav');if(btn)btn.classList.add('active');
 document.querySelectorAll('#mobileBottomNav button').forEach(x=>x.classList.toggle('active',(x.dataset.tab==='devices'||x.dataset.mobileTab==='devices')));
 const card=$('billingStopPausePolicyCard');if(card)card.scrollIntoView({behavior:'smooth',block:'center'});
 void loadBillingStopPausePolicy();
}
function billingStopPausePolicyMessage(text,error){const el=$('billingStopPausePolicyMessage');if(!el)return;el.textContent=String(text||'');el.style.borderLeftColor=error?'#ff4d6d':'var(--a)';}
function renderBillingStopPausePolicy(result){
 const enabled=result?.enabled===true,sw=$('billingStopPausePolicySwitch'),state=$('billingStopPausePolicyState'),save=$('billingStopPausePolicySave');
 if(sw){sw.checked=enabled;sw.disabled=!billingStopPausePolicyIsOwner();}
 if(state){state.textContent=enabled?'PAUSE / STOP DIIZINKAN':'PAUSE / STOP TERKUNCI';state.style.color=enabled?'var(--ok)':'#ff4d6d';state.style.borderColor=enabled?'var(--ok)':'#ff4d6d';}
 if(save)save.disabled=!billingStopPausePolicyIsOwner();
 billingStopPausePolicyMessage(enabled?'Database mengizinkan penyewa menggunakan PAUSE / STOP. PC memeriksa ulang izin saat tombol ditekan.':'PAUSE / STOP penyewa dikunci. Timer tetap berjalan; kontrol Admin dan akhir waktu otomatis tetap tersedia.',false);
}
async function loadBillingStopPausePolicy(){
 const sw=$('billingStopPausePolicySwitch'),save=$('billingStopPausePolicySave'),state=$('billingStopPausePolicyState');
 try{
  if(state)state.textContent='MEMUAT...';if(sw)sw.disabled=true;if(save)save.disabled=true;
  const result=await rpc('admin_get_billing_stop_pause_policy',{});
  if(!result||typeof result.enabled!=='boolean')throw new Error('Respons izin PAUSE / STOP tidak valid.');
  renderBillingStopPausePolicy(result);
  if(!billingStopPausePolicyIsOwner()){if(sw)sw.disabled=true;if(save)save.disabled=true;billingStopPausePolicyMessage('Hanya Master/Owner yang boleh mengubah izin PAUSE / STOP.',false);}
  return result;
 }catch(e){if(state)state.textContent='GAGAL MEMUAT';if(sw)sw.disabled=true;if(save)save.disabled=true;billingStopPausePolicyMessage('Status izin tidak bisa diverifikasi. Jangan menganggap akses terbuka. Detail: '+String(e?.message||e).slice(0,180),true);return null;}
}
async function saveBillingStopPausePolicy(){
 if(!billingStopPausePolicyIsOwner()){billingStopPausePolicyMessage('Hanya Master/Owner yang boleh mengubah izin PAUSE / STOP.',true);return;}
 const sw=$('billingStopPausePolicySwitch'),save=$('billingStopPausePolicySave');if(!sw||!save)return;
 const enabled=sw.checked===true,action=enabled?'MEMBUKA':'MENGUNCI';
 const warning=enabled?'Penyewa bisa menggunakan PAUSE / STOP dan tombol X pada timer PC.':'PC mengunci PAUSE / STOP penyewa pada pemeriksaan berikutnya. Timer tetap berjalan.';
 if(!confirm(action+' akses PAUSE / STOP BILLING?'+'\n\n'+warning+'\n\nKontrol jarak jauh Admin dan akhir waktu otomatis tidak berubah.')){await loadBillingStopPausePolicy();return;}
 save.disabled=true;
 try{
  const result=await rpc('admin_set_billing_stop_pause_policy',{p_enabled:enabled});
  if(!result||result.enabled!==enabled)throw new Error('Database tidak mengonfirmasi perubahan izin.');
  renderBillingStopPausePolicy(result);
  billingStopPausePolicyMessage(enabled?'TERSIMPAN: akses PAUSE / STOP dibuka. PC memeriksa izin saat penyewa menekan tombol.':'TERSIMPAN: akses PAUSE / STOP dikunci. PC menolak tindakan penyewa pada pemeriksaan berikutnya.',false);
  if(typeof msg==='function')msg(enabled?'Akses PAUSE / STOP Billing dibuka.':'Akses PAUSE / STOP Billing dikunci.');
 }catch(e){if(sw)sw.disabled=true;billingStopPausePolicyMessage('SIMPAN GAGAL / STATUS TIDAK DIKETAHUI. Muat ulang status dari database. Detail: '+String(e?.message||e).slice(0,180),true);}
 finally{save.disabled=!billingStopPausePolicyIsOwner();}
}
"""
page=page[:anchor.start()]+"\n\n"+functions+"\n\n"+page[anchor.start():]

if gradle.count("versionCode 78")!=1 or gradle.count("versionName '12.1.50'")!=1: raise SystemExit("Admin Gradle version anchor mismatch")
gradle=gradle.replace("versionCode 78","versionCode 79",1).replace("versionName '12.1.50'","versionName '12.1.51'",1)
if gradle.count("applicationId 'com.anigames.billingadmin.v150'")!=1: raise SystemExit("Admin applicationId anchor mismatch")
gradle=gradle.replace("applicationId 'com.anigames.billingadmin.v150'","applicationId 'com.anigames.billingadmin.v151'",1)
manifest,n=re.subn(r'android:label="[^"]+"','android:label="AniGames Admin V12.1.51"',manifest,count=1)
if n!=1: raise SystemExit("Admin manifest label anchor mismatch")

for token in [MARKER,"billingStopPausePolicyNav","billingStopPausePolicyCard","admin_get_billing_stop_pause_policy","admin_set_billing_stop_pause_policy"]:
    if token not in page: raise SystemExit("Missing Admin policy token: "+token)
if page.count('id="billingStopPausePolicySwitch"')!=1 or page.count('id="billingStopPausePolicySave"')!=1: raise SystemExit("Duplicate Admin control id")

PAGE.write_text(page,encoding="utf-8")
GRADLE.write_text(gradle,encoding="utf-8")
MANIFEST.write_text(manifest,encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.51 — Owner-controlled PC Billing PAUSE / STOP permission, based on V12.1.50 DB Android.\n",encoding="utf-8")
print("PASS: Admin V12.1.51 Owner-only PAUSE/STOP menu and single checkbox.")
