## Tuned results
| Method | Parameters (TAGP) | Clean trials | Disturbed trials | Heading | Inclination |
|---|---|---|---|---|---|
| Madgwick | gain = 0.07 | 4.3° | 5.4° | 3.9° | 2.5° |
| Mahony | k_I = 0.001, k_P = 1 | 6.8° | 9.2° | 6.3° | 4.2° |
| VQF | tauAcc = 3, tauMag = 20 | 1.8° | 2.7° | 2.0° | 0.7° |
| ESKF (ours) | acc_noise = 0.1, mag_noise = 1 | 2.5° | 3.6° | 2.7° | 0.9° |
| ESKF + gating (ours) | acc_noise = 0.05, mag_noise = 0.3 | 2.1° | 2.6° | 2.1° | 0.8° |

## Mean total error by kind of trial
| Trials | n | Madgwick | Mahony | VQF | ESKF (ours) | ESKF + gating (ours) |
|---|---|---|---|---|---|---|
| slow rotation | 5 | 2.1° | 2.9° | **1.4°** | 2.8° | 1.8° |
| fast rotation | 4 | 3.6° | 3.9° | **2.9°** | 3.9° | 3.4° |
| slow translation | 5 | 2.6° | 4.5° | **1.0°** | 1.3° | 1.5° |
| fast translation | 4 | 8.1° | 17.3° | **1.0°** | 1.4° | 1.5° |
| slow combined | 2 | 2.6° | 1.8° | 1.1° | **0.9°** | 1.2° |
| fast combined | 3 | 7.8° | 10.1° | 3.5° | 4.3° | **3.5°** |
| tapping | 2 | 2.4° | 3.9° | 1.6° | **1.4°** | 1.5° |
| phone vibration | 2 | 7.4° | 5.0° | 4.3° | 4.3° | **4.2°** |
| stationary magnet | 4 | 4.5° | 10.4° | **2.6°** | 3.9° | 2.8° |
| attached magnet | 5 | 6.9° | 14.3° | 3.1° | 3.8° | **2.4°** |
| office | 2 | 5.6° | 4.6° | **1.8°** | 4.7° | 3.1° |
| mixed | 1 | 2.9° | 7.6° | **1.1°** | 1.2° | 1.1° |

## Worst three trials per method
| Method | Worst | 2nd | 3rd |
|---|---|---|---|
| Madgwick | 15_undisturbed_fast_translation_A (14.3°) | 32_disturbed_attached_magnet_1cm (13.7°) | 23_undisturbed_fast_combined_360s (9.9°) |
| Mahony | 32_disturbed_attached_magnet_1cm (45.4°) | 18_undisturbed_fast_translation_with_breaks_B (30.7°) | 16_undisturbed_fast_translation_B (20.3°) |
| VQF | 27_disturbed_phone_vibration_B (6.9°) | 32_disturbed_attached_magnet_1cm (6.0°) | 08_undisturbed_fast_rotation_with_breaks_A (4.9°) |
| ESKF (ours) | 32_disturbed_attached_magnet_1cm (8.9°) | 08_undisturbed_fast_rotation_with_breaks_A (7.8°) | 21_undisturbed_fast_combined (7.0°) |
| ESKF + gating (ours) | 27_disturbed_phone_vibration_B (6.6°) | 08_undisturbed_fast_rotation_with_breaks_A (5.9°) | 21_undisturbed_fast_combined (4.9°) |

## Out-of-sample check of the tuning (mean total error)
| Method | Tuned on all 39 trials | Each trial tuned on the other 38 |
|---|---|---|
| Madgwick | 4.73° | 4.73° |
| Mahony | 7.77° | 8.07° |
| VQF | 2.13° | 2.13° |
| ESKF (ours) | 2.91° | 3.05° |
| ESKF + gating (ours) | 2.34° | 2.34° |
