package com.anigames.aniwolrelay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class MagicPacketSenderTest {
    @Test fun standardMagicPacketIs102BytesAndRepeatsMac16Times() {
        val packet = MagicPacketSender.buildPayload("74:56:3C:A5:B4:22")
        assertEquals(102, packet.size)
        for (i in 0 until 6) assertEquals(0xFF.toByte(), packet[i])
        val mac = byteArrayOf(0x74,0x56,0x3C,0xA5.toByte(),0xB4.toByte(),0x22)
        for (repeat in 0 until 16) for (index in 0 until 6)
            assertEquals(mac[index], packet[6 + repeat * 6 + index])
    }
    @Test fun acceptsDashAndCompactMacFormats() {
        assertEquals(102, MagicPacketSender.buildPayload("74-56-3C-A5-B4-22").size)
        assertEquals(102, MagicPacketSender.buildPayload("74563CA5B422").size)
    }
    @Test fun rejectsInvalidAndNonUnicastMacs() {
        assertThrows(IllegalArgumentException::class.java) { MagicPacketSender.buildPayload("not-a-mac") }
        assertThrows(IllegalArgumentException::class.java) { MagicPacketSender.buildPayload("00:00:00:00:00:00") }
        assertThrows(IllegalArgumentException::class.java) { MagicPacketSender.buildPayload("FF:FF:FF:FF:FF:FF") }
    }
}