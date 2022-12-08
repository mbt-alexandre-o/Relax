"""
TODO docstring
"""
import click
from pathlib import Path
import os
from datetime import date
import mne
import numpy as np
import matplotlib.pyplot as plt
import json

from alive_progress import alive_bar
from relax.egg_feedback import egg_modulation, GAS_DOWN, EGG_BUFFER_DURATION
from relax.ecg_feedback import ecg_modulation, ECG_BUFFER_DURATION
from relax.resp_feedback import resp_modulation, RESP_BUFFER_DURATION
from relax.data_array import DataArray

SAMP_FREQ = 64

def plot_mod(ecg_mod,resp_mod,egg_mod):
    fig, axs = plt.subplots(3, 1, sharex=True)
    fig.subplots_adjust(hspace=0)
    axs[-1].set_xlabel("time (s)")
    axs[0].plot([x/SAMP_FREQ for x in range(len(ecg_mod))], ecg_mod)
    axs[1].plot([x/SAMP_FREQ for x in range(len(resp_mod))], resp_mod)
    axs[2].plot([x/SAMP_FREQ for x in range(len(egg_mod))], egg_mod)
    plt.show()

def get_resp_modulation(sfreq,resp_data):
    """
    TODO docstring
    """
    mod_array = []
    samp_size = int(sfreq/SAMP_FREQ)
    buffer = DataArray(RESP_BUFFER_DURATION * sfreq)
    index_list = np.arange(0,len(resp_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            resp = resp_data[index:index+samp_size]
            if len(resp)>0:
                mod = resp_modulation(resp,buffer)
                if mod != -1.0:
                    mod_array.append(mod)
            bar()
    return mod_array


def get_egg_modulation(sfreq, egg_data, egg_freq):
    """
    TODO docstring
    """
    mod_array = []
    samp_size = int(sfreq/SAMP_FREQ)
    down_sr = sfreq / GAS_DOWN
    len_buffer = int(EGG_BUFFER_DURATION * down_sr)
    buffer = DataArray(len_buffer, down=GAS_DOWN)
    med_buffer = DataArray(len_buffer)
    filter_buffer = DataArray(len_buffer)
    time_abscissa = np.array([x / down_sr for x in range(len_buffer)])
    index_list = np.arange(0,len(egg_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            egg = egg_data[index:index+samp_size]
            if len(egg)>0:
                mod = egg_modulation(egg,buffer,med_buffer,filter_buffer,time_abscissa,down_sr,egg_freq)
                if mod != -1.0:
                    mod_array.append(mod)
            bar()
    return mod_array

def get_ecg_modulation(sfreq,ecg_data):
    """
    TODO docstring
    """
    heart_beat = []
    samp_size = int(sfreq/SAMP_FREQ)
    last_time = 0
    last_ecg_point = 0
    buffer = DataArray(ECG_BUFFER_DURATION * sfreq)
    index_list = np.arange(0,len(ecg_data),samp_size)
    with alive_bar(len(index_list)) as bar:
        for index in index_list:
            ecg = ecg_data[index:index+samp_size]
            if len(ecg)>0:
                array = ecg_modulation(ecg,last_ecg_point,buffer,last_time,index/sfreq)
                last_ecg_point = array[0]
                if len(array)==2:
                    last_time = array[1]
                    heart_beat.append(1)
                else:
                    heart_beat.append(0)
            bar()
    return heart_beat

@click.command()
@click.option("--subject_id", prompt="Subject id")
@click.option("--egg_electrod",type = int, prompt="Egg electrod")
@click.option("--egg_freq",type = float, prompt="Egg freq")
def create_mock_soundscapes(subject_id,egg_electrod,egg_freq):
    """
    TODO docstring
    """
    record_folder = Path(__file__).parent / "../records/"
    file_list = os.listdir(record_folder)
    expected_file = f"RS_{str(date.today())}_{subject_id}.fif"
    if expected_file in file_list:
        print("Resting state file founded.")
        raw = mne.io.Raw(str(record_folder/expected_file))
        sfreq = raw.info['sfreq']
        resp_data = raw.get_data(["Resp"])[0]
        ecg_data = raw.get_data(["EGG2ECG"])[0] - raw.get_data(["EGG8ECG"])[0]
        egg_data = raw.get_data([f"EGG{egg_electrod}"])[0]
        ecg_mod = get_ecg_modulation(sfreq,ecg_data)
        resp_mod = get_resp_modulation(sfreq,resp_data)
        egg_mod = get_egg_modulation(sfreq,egg_data,egg_freq)
        dict_ = {
            "ecg_mod":ecg_mod,
            "resp_mod":resp_mod,
            "egg_mod":egg_mod,
            "time":[x/SAMP_FREQ for x in range(len(ecg_mod))]
        }
        save_file = f"mock-modulation_{str(date.today())}_{subject_id}.json"
        with open(str(record_folder/save_file),"w") as f:
            json.dump(dict_,f)
        plot_mod(ecg_mod,resp_mod,egg_mod)
    else:
        print(f"{expected_file} was not found.")

if __name__ == "__main__":
    create_mock_soundscapes()
