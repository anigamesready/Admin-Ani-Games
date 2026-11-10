package com.anigames.aniwolrelay
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface

object MagicPacketSender {
    data class SendResult(val sent: Int, val destinations: List<String>)
    fun send(macAddress: String): SendResult {
        val mac = macAddress.replace(":", "").replace("-", "").trim().uppercase()
        require(mac.matches(Regex("^[0-9A-F]{12}$"))) { "MAC LAN target tidak valid" }
        val bytes = mac.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        val packet = ByteArray(102)
        for (i in 0 until 6) packet[i] = 0xFF.toByte()
        for (i in 0 until 16) System.arraycopy(bytes, 0, packet, 6 + i * 6, 6)
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
        if (sent == 0) throw IllegalStateException("Magic Packet tidak berhasil dikirim melalui Wi-Fi")
        return SendResult(sent, labels.distinct())
    }
}
