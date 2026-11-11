package com.anigames.aniwolrelay
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface

object MagicPacketSender {
    data class SendResult(val sent: Int, val destinations: List<String>)
    internal fun buildPayload(macAddress: String): ByteArray {
        val mac = macAddress.replace(":", "").replace("-", "").trim().uppercase()
        require(mac.matches(Regex("^[0-9A-F]{12}$"))) { "MAC LAN target tidak valid" }
        require(mac != "000000000000" && mac != "FFFFFFFFFFFF") { "MAC LAN target tidak valid" }
        val bytes = mac.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        return ByteArray(102).apply {
            for (i in 0 until 6) this[i] = 0xFF.toByte()
            for (i in 0 until 16) System.arraycopy(bytes, 0, this, 6 + i * 6, 6)
        }
    }
    fun send(macAddress: String): SendResult {
        val packet = buildPayload(macAddress)
        val destinations = linkedSetOf<InetAddress>()
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val network = interfaces.nextElement()
                if (!network.isUp || network.isLoopback || network.isVirtual) continue
                for (address in network.interfaceAddresses) {
                    val broadcast = address.broadcast
                    if (address.address is Inet4Address && broadcast != null) destinations.add(broadcast)
                }
            }
        } catch (_: Exception) { }
        destinations.add(InetAddress.getByName("255.255.255.255"))
        var sent = 0
        val labels = mutableListOf<String>()
        DatagramSocket().use { socket ->
            socket.broadcast = true
            for (destination in destinations) for (port in listOf(9, 7)) {
                try {
                    socket.send(DatagramPacket(packet, packet.size, destination, port))
                    sent++
                    labels.add("${destination.hostAddress}:$port")
                } catch (_: Exception) { }
            }
        }
        if (sent == 0) throw IllegalStateException("Magic Packet tidak berhasil dikirim melalui jaringan lokal")
        return SendResult(sent, labels.distinct())
    }
}