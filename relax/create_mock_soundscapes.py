"""
TODO docstring
"""
import json
import os
from datetime import date
from pathlib import Path
from random import randint

import click
import mne
import numpy as np
from alive_progress import alive_bar

from relax.bufferQueue import BufferQueue
from relax.ecg_feedback import ECG_BUFFER_DURATION, ecg_modulation
from relax.egg_feedback import EGG_BUFFER_DURATION, GAS_DOWN, egg_modulation
from relax.resp_feedback import RESP_BUFFER_DURATION, resp_modulation

SAMP_FREQ = 64


def get_half_crossing(data, padding):
    """
    Function that return the index of the points in the input data that cross
    the 0.5 during a decreasing phase.

    Parameters
    ----------
    data: Array of Float
        Computed volume of a layer of the resting state
    padding: Int
        How much point before the computated point is used to know if we are in
        a decreasing phase
    Returns
    -------
    crossing_points: Array of Int
        Index of the points in the input data that cross the 0.5 during a
        decreasing phase
    """
    crossing_points = []
    for i in range(padding, len(data)):
        if (
            data[i - 1] > 0.5
            and data[i] <= 0.5
            and np.mean(data[i - padding : i]) > 0.5
        ):
            crossing_points.append(i)
    return crossing_points


def get_recomposed_mock(data, n_recomposed, padding=128):
    """
    Function that return shuffle volume array cut in 0.5 crossing.

    Parameters
    ----------
    data: Array of Float
        Computed volume of a layer of the resting state
    n_recomposed: Int
        How much shuffled volume to return
    padding: Int
        The padding used to get 0.5 crossing

    Returns
    -------
    recomposed_mock: Array of size n_recomposed of Array of Float
        Array of shuffled volume array
    """
    recomposed_mock = []
    crossing_points = get_half_crossing(data, padding)
    pstart = crossing_points[0]
    pend = crossing_points[-1]
    for _ in range(n_recomposed):
        pmid = crossing_points[randint(2, len(crossing_points) - 2)]
        recomposed = data[:pstart] + data[pmid:pend] + data[pstart:pmid] + data[pend:]
        recomposed_mock.append(recomposed)
    return recomposed_mock


def add_recomposed_mock_to_dict(dict_):
    """
    Function that add shuffle volume array in a dictionary.

    Parameters
    ----------
    dict_: Dictionaty
        Dictionary containing the computed volume of the different layers of the
        subject resting state
    """
    for key in ["ecg_or", "egg_or", "resp_or"]:
        data = dict_[key]
        if key == "ecg_or":
            padding = 1
        else:
            padding = 128
        recomposed_mock = get_recomposed_mock(data, 4, padding)
        for i, shuffle_volume in enumerate(recomposed_mock):
            dict_[key.replace("_or", "_" + str(i + 1))] = shuffle_volume


def get_resp_modulation(sfreq, resp_data):
    """
    TODO docstring
    """
    mod_array = []
    samp_size = int(sfreq / SAMP_FREQ)
    buffer = BufferQueue(RESP_BUFFER_DURATION * sfreq)
    index_list = np.arange(0, len(resp_data), samp_size)
    with alive_bar(len(index_list)) as progress_bar:
        for index in index_list:
            resp = resp_data[index : index + samp_size]
            if len(resp) > 0:
                mod = resp_modulation(resp, buffer, sfreq)
                if mod != -1.0:
                    mod_array.append(mod)
            progress_bar()
    return mod_array


def get_egg_modulation(sfreq, egg_data, egg_freq):
    """
    TODO docstring
    """
    mod_array = []
    last_mod = -1
    samp_size = int(sfreq / SAMP_FREQ)
    down_sr = sfreq / GAS_DOWN
    len_buffer = int(EGG_BUFFER_DURATION * down_sr)
    buffer = BufferQueue(len_buffer, down=GAS_DOWN)
    med_buffer = BufferQueue(len_buffer)
    filter_buffer = BufferQueue(len_buffer)
    time_abscissa = np.array([x / down_sr for x in range(len_buffer)])
    index_list = np.arange(0, len(egg_data), samp_size)
    with alive_bar(len(index_list)) as progress_bar:
        for index in index_list:
            egg = egg_data[index : index + samp_size]
            i = int(index / samp_size)
            if len(egg) > 0:
                mod = egg_modulation(
                    egg,
                    buffer,
                    med_buffer,
                    filter_buffer,
                    time_abscissa,
                    down_sr,
                    egg_freq,
                    last_mod,
                    1 / SAMP_FREQ,
                )
                if mod != -1.0:
                    mod_array.append(mod)
                last_mod = mod
            progress_bar()
    return mod_array


def get_ecg_modulation(sfreq, ecg_data):
    """
    TODO docstring
    """
    heart_beat = []
    samp_size = int(sfreq / SAMP_FREQ)
    last_time = 0
    last_ecg_point = 0
    buffer = BufferQueue(ECG_BUFFER_DURATION * sfreq)
    index_list = np.arange(0, len(ecg_data), samp_size)
    with alive_bar(len(index_list)) as progress_bar:
        for index in index_list:
            ecg = ecg_data[index : index + samp_size]
            if len(ecg) > 0:
                time = ecg_modulation(
                    ecg, last_ecg_point, buffer, last_time, index / sfreq
                )
                if time != last_time:
                    last_time = time
                    heart_beat.append(1)
                else:
                    heart_beat.append(0)
                last_ecg_point = ecg[-1]
            progress_bar()
    return heart_beat


@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--egg_electrod", type=int, prompt="Egg electrod")
@click.option("--egg_freq", type=float, prompt="Egg freq")
@click.option("--day", type=str, prompt="Date", default=str(date.today()))
def create_mock_soundscapes(subject_id, egg_electrod, egg_freq, day):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    file_list = os.listdir(record_folder)
    expected_file = f"RS_{day}_{subject_id}.fif"
    if expected_file in file_list:
        print("Resting state file founded.")
        raw = mne.io.Raw(str(record_folder / expected_file))
        sfreq = raw.info["sfreq"]
        resp_data = raw.get_data(["Resp"])[0]
        ecg_data = raw.get_data(["EGG2ECG"])[0] - raw.get_data(["EGG8ECG"])[0]
        egg_data = raw.get_data([f"EGG{egg_electrod}"])[0]
        ecg_mod = get_ecg_modulation(sfreq, ecg_data)
        resp_mod = get_resp_modulation(sfreq, resp_data)
        egg_mod = get_egg_modulation(sfreq, egg_data, egg_freq)
        dict_ = {
            "ecg_or": ecg_mod,
            "resp_or": resp_mod,
            "egg_or": egg_mod,
            "time": [x / SAMP_FREQ for x in range(len(ecg_mod))],
        }
        add_recomposed_mock_to_dict(dict_)
        save_file = f"mock-modulation_{day}_{subject_id}.json"
        with open(str(record_folder / save_file), "w") as f:
            json.dump(dict_, f)
    else:
        print(f"{expected_file} was not found.")


if __name__ == "__main__":
    create_mock_soundscapes()
