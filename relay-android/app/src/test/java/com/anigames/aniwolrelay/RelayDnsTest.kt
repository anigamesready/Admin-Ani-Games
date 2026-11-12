package com.anigames.aniwolrelay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RelayDnsTest {
    @Test
    fun parsesIpv4AndIpv6AnswersAndUsesLowestTtl() {
        val result = RelayDns.parseDnsJson(
            """{"Status":0,"Answer":[
                {"name":"example.com","type":5,"TTL":300,"data":"edge.example.com"},
                {"name":"example.com","type":1,"TTL":120,"data":"203.0.113.10"},
                {"name":"example.com","type":28,"TTL":90,"data":"2001:db8::10"},
                {"name":"example.com","type":16,"TTL":30,"data":"ignored"}
            ]}"""
        )
        assertEquals(2, result.addresses.size)
        assertTrue(result.addresses.any { it.hostAddress == "203.0.113.10" })
        assertTrue(result.addresses.any { it.hostAddress.contains("2001:db8") })
        assertEquals(90L, result.ttlSeconds)
    }

    @Test
    fun returnsEmptyResultForDnsFailureStatus() {
        val result = RelayDns.parseDnsJson("""{"Status":3}""")
        assertTrue(result.addresses.isEmpty())
    }

    @Test
    fun ignoresMalformedAddressRecords() {
        val result = RelayDns.parseDnsJson(
            """{"Status":0,"Answer":[{"type":1,"TTL":60,"data":"999.1.1.1"}]}"""
        )
        assertTrue(result.addresses.isEmpty())
    }
}
