import unittest

from vision.trophy_observer import TrophyObserver


class TrophyObserverTests(unittest.TestCase):
    def test_trio_showdown_first_place_starts_at_eleven_trophies(self):
        observer = TrophyObserver(["shelly"])
        observer.current_trophies = 0

        self.assertEqual(observer.calc_showdown_delta(0), 11)


if __name__ == "__main__":
    unittest.main()
