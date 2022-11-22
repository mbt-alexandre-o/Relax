"""
TODO docstring
"""
import os
import random
import time
import wave
from math import floor

import numpy as np
from relax.data_array import DataArray

ECG_BUFFER_DURATION = 2


def get_random_file(folder):
    """
    TODO docstring
    """
    file = random.choice(os.listdir(folder))
    return folder + "/" + file


def get_random_wf(folder):
    """
    TODO docstring
    """
    return wave.open(get_random_file(folder), "rb")


def get_ecg_wav(biofeedback):
    """
    TODO docstring
    """
    sc_dur = biofeedback.SOUNDSCAPE_DURATION

    if biofeedback.audio_start == 0:
        index = 0
    else:
        t_point = time.time() - biofeedback.audio_start
        index = floor(t_point / sc_dur)
    folder = biofeedback.soundscapes_folders[index]
    return get_random_wf(folder + "/ecg")


def ecg_feedback(biofeedback):
    """
    TODO docstring
    """
    if biofeedback.state == "ecg":
        wav_buffer = [get_ecg_wav(biofeedback), get_ecg_wav(biofeedback)]
        wav_index = 0
        buffer = DataArray(ECG_BUFFER_DURATION * biofeedback.sampling_rate)
        last_ecg_point = 0
        last_time = time.time()
        num_smp, num_evt = biofeedback.ft_ecg.wait(
            biofeedback.header_ecg.nSamples, biofeedback.header_ecg.nEvents, 500
        )
        while biofeedback.recording:
            new_smp, new_evt = biofeedback.ft_ecg.wait(num_smp, num_evt, 500)
            if new_smp == num_smp:
                continue
            data_sample = np.array(biofeedback.ft_ecg.getData([num_smp, new_smp - 1])).T
            ecg = (
                data_sample[biofeedback.ecg_poses[0]]
                - data_sample[biofeedback.ecg_poses[1]]
            )
            d_ecg = np.diff([last_ecg_point] + ecg)
            last_ecg_point = ecg[-1]
            buffer.add_data(d_ecg)
            if buffer.full():
                if not biofeedback.audio_on:
                    biofeedback.audio_on = True
                min_decg = min(d_ecg)
                prop = buffer.prop(min_decg)
                if prop < 0.2 and time.time() - last_time > 0.5:
                    biofeedback.ecg_wav = wav_buffer[wav_index]
                    last_time = time.time()
                    biofeedback.ecg_ts.append(last_time)
                    wav_index = (wav_index + 1) % 2
                    wav_buffer[wav_index] = get_ecg_wav(biofeedback)

            num_smp = new_smp
            num_evt = new_evt
