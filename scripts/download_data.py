"""Download the BROAD dataset (Laidig et al., 2021, CC BY 4.0) into data/broad_hdf5/.

Source: https://github.com/dlaidig/broad (folder data_hdf5, about 170 MB).
Files that are already there are skipped.
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/dlaidig/broad/main/data_hdf5/"
TRIALS = [
    "01_undisturbed_slow_rotation_A",
    "02_undisturbed_slow_rotation_B",
    "03_undisturbed_slow_rotation_C",
    "04_undisturbed_slow_rotation_with_breaks_A",
    "05_undisturbed_slow_rotation_with_breaks_B",
    "06_undisturbed_fast_rotation_A",
    "07_undisturbed_fast_rotation_B",
    "08_undisturbed_fast_rotation_with_breaks_A",
    "09_undisturbed_fast_rotation_with_breaks_B",
    "10_undisturbed_slow_translation_A",
    "11_undisturbed_slow_translation_B",
    "12_undisturbed_slow_translation_C",
    "13_undisturbed_slow_translation_with_breaks_A",
    "14_undisturbed_slow_translation_with_breaks_B",
    "15_undisturbed_fast_translation_A",
    "16_undisturbed_fast_translation_B",
    "17_undisturbed_fast_translation_with_breaks_A",
    "18_undisturbed_fast_translation_with_breaks_B",
    "19_undisturbed_slow_combined_240s",
    "20_undisturbed_slow_combined_360s",
    "21_undisturbed_fast_combined",
    "22_undisturbed_fast_combined_240s",
    "23_undisturbed_fast_combined_360s",
    "24_disturbed_tapping_A",
    "25_disturbed_tapping_B",
    "26_disturbed_phone_vibration_A",
    "27_disturbed_phone_vibration_B",
    "28_disturbed_stationary_magnet_A",
    "29_disturbed_stationary_magnet_B",
    "30_disturbed_stationary_magnet_C",
    "31_disturbed_stationary_magnet_D",
    "32_disturbed_attached_magnet_1cm",
    "33_disturbed_attached_magnet_2cm",
    "34_disturbed_attached_magnet_3cm",
    "35_disturbed_attached_magnet_4cm",
    "36_disturbed_attached_magnet_5cm",
    "37_disturbed_office_A",
    "38_disturbed_office_B",
    "39_disturbed_mixed",
]


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/broad_hdf5")
    out.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(TRIALS, 1):
        path = out / f"{name}.hdf5"
        if path.exists():
            continue
        print(f"[{i:2d}/{len(TRIALS)}] {name}", flush=True)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(BASE + path.name, tmp)
        tmp.rename(path)
    print(f"{len(TRIALS)} trials in {out}")


if __name__ == "__main__":
    main()
