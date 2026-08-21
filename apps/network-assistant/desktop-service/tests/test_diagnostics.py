import unittest

from diagnostics import find_peer, parse_ping_output


class ParsePingOutputTests(unittest.TestCase):
    def test_derp_samples(self):
        output = "\n".join(
            [
                "pong from v2359a (100.93.178.121) via DERP(hkg) in 106ms",
                "pong from v2359a (100.93.178.121) via DERP(hkg) in 94ms",
            ]
        )
        result = parse_ping_output(output, attempted=3)
        self.assertEqual(result["path"], "derp")
        self.assertEqual(result["relay"], "hkg")
        self.assertEqual(result["received"], 2)
        self.assertEqual(result["loss_pct"], 33.3)
        self.assertEqual(result["rtt_ms"]["p50"], 100.0)

    def test_last_successful_sample_is_current_path(self):
        output = "\n".join(
            [
                "pong from v2359a (100.93.178.121) via DERP(hkg) in 88ms",
                "pong from v2359a (100.93.178.121) via [2409:8a1e:1234::99]:41641 in 21ms",
                "pong from v2359a (100.93.178.121) via [2409:8a1e:1234::99]:41641 in 23ms",
            ]
        )
        result = parse_ping_output(output, attempted=3)
        self.assertEqual(result["path"], "direct_ipv6")
        self.assertTrue(result["direct_established"])
        self.assertEqual(result["path_samples"]["derp"], 1)
        self.assertEqual(result["path_samples"]["direct_ipv6"], 2)
        self.assertEqual(result["rtt_ms"]["p50"], 22.0)

    def test_later_derp_replaces_earlier_direct_path(self):
        output = "\n".join(
            [
                "pong from v2359a (100.93.178.121) via [2409:8a1e:1234::99]:41641 in 23ms",
                "pong from v2359a (100.93.178.121) via DERP(hkg) in 91ms",
                "pong from v2359a (100.93.178.121) via DERP(hkg) in 95ms",
            ]
        )
        result = parse_ping_output(output, attempted=3)
        self.assertEqual(result["path"], "derp")
        self.assertFalse(result["direct_established"])
        self.assertEqual(result["relay"], "hkg")
        self.assertEqual(result["path_transitions"], ["direct_ipv6", "derp"])

    def test_peer_relay(self):
        output = "pong from phone (100.64.0.2) via peer-relay(microcavities) in 31ms"
        result = parse_ping_output(output, attempted=1)
        self.assertEqual(result["path"], "peer_relay")


class FindPeerTests(unittest.TestCase):
    def setUp(self):
        self.status = {
            "Peer": {
                "peer-map-key-not-returned": {
                    "ID": "nRTw9d13G311CNTRL",
                    "HostName": "V2359A",
                    "DNSName": "v2359a.example.ts.net.",
                    "TailscaleIPs": ["100.93.178.121", "fd7a::1"],
                }
            }
        }

    def test_find_by_host_name_case_insensitive(self):
        peer = find_peer(self.status, "v2359a")
        self.assertEqual(peer["ID"], "nRTw9d13G311CNTRL")

    def test_find_by_stable_id(self):
        peer = find_peer(self.status, "nRTw9d13G311CNTRL")
        self.assertEqual(peer["HostName"], "V2359A")


if __name__ == "__main__":
    unittest.main()
