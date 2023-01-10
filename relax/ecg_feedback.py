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


def ecg_modulation(ecg, last_ecg_point, buffer, last_time, now):
    """
    TODO docstring
    """
    d_ecg = np.diff([last_ecg_point] + ecg)
    returned_array = [ecg[-1]]
    buffer.add_data(d_ecg)
    if buffer.full():
        if len(d_ecg)>0:
            min_decg = min(d_ecg)
            prop = buffer.prop(min_decg)
            if prop < 0.2 and now - last_time > 0.5:
                returned_array.append(now)
    return returned_array


def ecg_feedback(biofeedback,test=False):
    """
    TODO docstring
    """
    print("Ecg thread started")
    if biofeedback.state == "ecg":
        biofeedback.ecg_wavs = [get_ecg_wav(biofeedback), get_ecg_wav(biofeedback)]
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
                    old_index = biofeedback.ecg_index
                    biofeedback.ecg_index = (biofeedback.ecg_index + 1) % 2
                    last_time = time.time()
                    biofeedback.ecg_ts.append(last_time)
                    biofeedback.ecg_wavs[old_index] = get_ecg_wav(biofeedback)

            num_smp = new_smp
            num_evt = new_evt
        print("Ecg thread finished")
    elif not test:
        biofeedback.ecg_wavs = [get_ecg_wav(biofeedback), get_ecg_wav(biofeedback)]
        last_index = 0
        new_index = 0
        mock_time = biofeedback.mock_time
        mock_ecg = biofeedback.mock_ecg

        while not biofeedback.audio_on:
            time.sleep(0.1)

        while biofeedback.recording:
            in_mock_time = time.time() - biofeedback.audio_start
            for i in range(last_index,len(mock_time)-1):
                if mock_time[i] <= in_mock_time and mock_time[i+1] > in_mock_time:
                    new_index = i
                    break
            if 1 in mock_ecg[last_index:new_index]:
                old_index = biofeedback.ecg_index
                biofeedback.ecg_index = (biofeedback.ecg_index + 1) % 2
                biofeedback.ecg_ts.append(time.time())
                biofeedback.ecg_wavs[old_index] = get_ecg_wav(biofeedback)
            last_index = new_index
            time.sleep(0.01)
        print("Ecg thread finished")
