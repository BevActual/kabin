import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from kabin.config import Config


class TestConfig(unittest.TestCase):
    def test_defaults_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertEqual(config.rom_dirs, [])
            self.assertEqual(config.hidden, [])
            self.assertTrue(config.sources["steam"])
            self.assertTrue(config.sources["book"])
            self.assertEqual(config.media_dirs, [])
            self.assertEqual(config.emulation["preset"], "balanced")
            self.assertEqual(config.artwork["steamgriddb_api_key"], "")
            self.assertTrue(config.artwork["openlibrary_covers"])
            self.assertEqual(config.covers, {})
            self.assertFalse(config.network["host_enabled"])
            self.assertEqual(config.streaming["sunshine_app"], "Desktop")
            self.assertEqual(config.streaming["resolution"], "1080")
            self.assertEqual(config.window["width"], 1100)
            self.assertFalse(config.window["maximized"])

    def test_persists_window_state_without_overwriting_restored_size_when_maximized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.save_window_state(900, 640, False)
            config.save_window_state(1920, 1080, True)

            restored = Config(path=path).window
            self.assertEqual((restored["width"], restored["height"]), (900, 640))
            self.assertTrue(restored["maximized"])

    def test_generates_and_persists_network_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            token = config.ensure_network_token()
            self.assertGreater(len(token), 32)
            self.assertEqual(Config(path=path).network["token"], token)

    def test_saves_paired_remote_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.save_remote_host(
                {"name": "Gaming PC", "address": "192.168.1.5", "port": 42424},
                "device-token",
            )
            remote = Config(path=path).network["remote_hosts"][0]
            self.assertEqual(remote["name"], "Gaming PC")
            self.assertEqual(remote["token"], "device-token")

    def test_removes_remote_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.save_remote_host(
                {"name": "Host", "address": "10.0.0.2", "port": 42424}, "token"
            )
            config.remove_remote_host("Host")
            self.assertEqual(config.network["remote_hosts"], [])

    def test_revoked_device_token_stops_authenticating(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            token = config.add_paired_device("Living Room")
            self.assertTrue(config.network_token_valid(token))
            config.remove_paired_device(0)
            self.assertFalse(config.network_token_valid(token))

    def test_round_trips_rom_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_rom_dir("/roms/snes", "SNES", ["sfc"], "echo {rom}")

            reloaded = Config(path=path)
            self.assertEqual(len(reloaded.rom_dirs), 1)
            self.assertEqual(reloaded.rom_dirs[0]["system"], "SNES")

    def test_persists_bios_path_with_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_rom_dir(
                "/games/ps2",
                "ps2",
                ["iso"],
                {"id": "pcsx2", "runtime": "managed", "executable": "/runtime/pcsx2"},
                "/firmware/ps2",
            )
            self.assertEqual(Config(path=path).rom_dirs[0]["bios_path"], "/firmware/ps2")

    def test_saved_config_is_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.artwork["steamgriddb_api_key"] = "secret"
            config.save()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_favorite_lookups_stay_correct_as_favorites_change(self):
        # is_favorite() is backed by a cached set (it runs once per library
        # item in several passes), so it has to notice every way the
        # underlying list changes: toggling, direct mutation, and a reload
        # replacing the list wholesale.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            self.assertFalse(config.is_favorite("steam:1"))

            config.toggle_favorite("steam:1")
            self.assertTrue(config.is_favorite("steam:1"))
            config.toggle_favorite("steam:1")
            self.assertFalse(config.is_favorite("steam:1"))

            # Direct mutation of the exposed list still reads back right.
            config.favorites.append("steam:2")
            self.assertTrue(config.is_favorite("steam:2"))
            config.favorites.remove("steam:2")
            self.assertFalse(config.is_favorite("steam:2"))

            # A reload replaces the list object entirely.
            config.toggle_favorite("roms:gba:zelda.gba")
            reloaded = Config(path=path)
            self.assertTrue(reloaded.is_favorite("roms:gba:zelda.gba"))
            self.assertFalse(reloaded.is_favorite("steam:1"))

    def test_concurrent_saves_do_not_corrupt_the_file(self):
        # Regression: save() wrote through one fixed ".config.json.tmp"
        # for every writer, so two racing saves - the GTK main thread
        # (favorites/recent/progress) and a ThreadingHTTPServer handler
        # thread while host mode is on - could leave a half-written
        # config.json. A config that then fails to parse falls back to
        # *all defaults*, dropping paired devices, remote hosts and
        # favorites.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.favorites.append("steam:1")
            errors = []

            def hammer(worker):
                for index in range(60):
                    try:
                        config.recent[f"worker{worker}:{index}"] = float(index)
                        config.save()
                        json.loads(path.read_text())
                    except Exception as exc:  # noqa: BLE001 - recording, not handling
                        errors.append(exc)

            threads = [threading.Thread(target=hammer, args=(n,)) for n in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            reloaded = Config(path=path)
            self.assertEqual(reloaded.favorites, ["steam:1"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            leftovers = list(Path(tmp).glob(".config.json*.tmp"))
            self.assertEqual(leftovers, [])

    def test_persists_chosen_cover_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cover = Path(tmp) / "jacket.jpg"
            cover.write_bytes(b"jpg")
            config = Config(path=path)
            config.set_cover("book:chamber.epub", str(cover))
            restored = Config(path=path)
            self.assertEqual(restored.cover_for("book:chamber.epub"), str(cover))
            restored.clear_cover("book:chamber.epub")
            self.assertEqual(Config(path=path).cover_for("book:chamber.epub"), "")

    def test_remove_rom_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_rom_dir("/roms/snes", "SNES", ["sfc"], "echo {rom}")
            config.add_rom_dir("/roms/gba", "GBA", ["gba"], "mgba {rom}")
            config.remove_rom_dir(0)
            self.assertEqual(len(config.rom_dirs), 1)
            self.assertEqual(config.rom_dirs[0]["system"], "GBA")

    def test_round_trips_media_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.add_media_dir("/media/books", "book")
            config.add_media_dir("/media/films", "video")
            config.remove_media_dir(0)
            restored = Config(path=path)
            self.assertEqual(restored.media_dirs, [{"path": "/media/films", "media_type": "video"}])

    def test_hide_and_unhide(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.hide("steam:553850", "Helldivers 2")
            self.assertTrue(config.is_hidden("steam:553850"))
            self.assertEqual(config.hidden_titles["steam:553850"], "Helldivers 2")
            config.unhide("steam:553850")
            self.assertFalse(config.is_hidden("steam:553850"))
            self.assertNotIn("steam:553850", config.hidden_titles)

    def test_ignores_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("not json")
            config = Config(path=path)
            self.assertEqual(config.rom_dirs, [])

    def test_wrong_typed_field_falls_back_to_its_default_instead_of_crashing(self):
        # A hand-edited (or stale-schema) config.json can parse fine as
        # JSON but have the wrong type for a field. Previously that value
        # replaced the default outright and crashed the first thing that
        # read it: `null` for "hidden" makes `x in config.hidden` raise
        # TypeError, a string for "network" makes `.setdefault(...)` on
        # it raise AttributeError.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"hidden": None, "network": "oops", "favorites": []}))
            config = Config(path=path)
            self.assertEqual(config.hidden, [])
            self.assertFalse(config.is_hidden("anything"))
            self.assertIsInstance(config.network, dict)
            self.assertEqual(config.network["port"], 42424)
            # A validly-typed field in the same file still loads normally.
            self.assertEqual(config.favorites, [])

    def test_non_dict_json_root_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("[1, 2, 3]")
            config = Config(path=path)
            self.assertEqual(config.rom_dirs, [])

    def test_recent_ids_ordered_most_recent_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            config.recent["steam:1"] = 100
            config.recent["steam:2"] = 300
            config.recent["steam:3"] = 200
            self.assertEqual(config.recent_ids(), ["steam:2", "steam:3", "steam:1"])

    def test_recent_ids_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            for i in range(5):
                config.recent[f"steam:{i}"] = i
            self.assertEqual(len(config.recent_ids(limit=2)), 2)

    def test_record_played_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.record_played("steam:553850")

            reloaded = Config(path=path)
            self.assertEqual(reloaded.recent_ids(), ["steam:553850"])
            self.assertEqual(reloaded.play_count("steam:553850"), 1)
            config.record_played("steam:553850")
            self.assertEqual(Config(path=path).play_count("steam:553850"), 2)

    def test_is_favorite_defaults_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertFalse(config.is_favorite("steam:553850"))

    def test_toggle_favorite_flips_state_and_returns_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            self.assertTrue(config.toggle_favorite("steam:553850"))
            self.assertTrue(config.is_favorite("steam:553850"))
            self.assertFalse(config.toggle_favorite("steam:553850"))
            self.assertFalse(config.is_favorite("steam:553850"))

    def test_favorite_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = Config(path=path)
            config.toggle_favorite("steam:553850")

            reloaded = Config(path=path)
            self.assertTrue(reloaded.is_favorite("steam:553850"))

    def test_migrates_legacy_config_to_kabin(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "omagames" / "config.json"
            legacy.parent.mkdir()
            legacy.write_text('{"favorites": ["steam:553850"]}')

            with patch.dict("os.environ", {"XDG_CONFIG_HOME": tmp}):
                config = Config()

            migrated = base / "kabin" / "config.json"
            self.assertTrue(config.is_favorite("steam:553850"))
            self.assertTrue(migrated.exists())
            self.assertIn("steam:553850", migrated.read_text())
            self.assertEqual(config._load_path, migrated)

    def test_library_fingerprint_ignores_activity_but_not_scan_inputs(self):
        # The window compares this before/after Settings to decide whether
        # closing it needs a full rescan.
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(path=Path(tmp) / "config.json")
            before = config.library_fingerprint()

            config.record_played("steam:1")
            config.record_play_time("steam:1", 600)
            config.save_window_state(1280, 720, False)
            self.assertEqual(config.library_fingerprint(), before)

            config.add_media_dir(tmp, "book")
            self.assertNotEqual(config.library_fingerprint(), before)

            changed = config.library_fingerprint()
            config.hide("steam:1")
            self.assertNotEqual(config.library_fingerprint(), changed)


if __name__ == "__main__":
    unittest.main()
