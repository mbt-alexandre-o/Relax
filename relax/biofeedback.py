"""
TODO docstring
"""
import json
import os
import random
import time
import wave
from datetime import date
from pathlib import Path
from threading import Thread

import click
import keyboard
import numpy as np
import serial

from relax.ecg_feedback import ecg_feedback
from relax.egg_feedback import egg_feedback
from relax.FieldTrip import Client
from relax.play_wav import play_wav
from relax.resp_feedback import resp_feedback


def trigger_loop(biofeedback):
    """
    TODO docstring
    """
    print("Trigger thread started")
    biofeedback.serial.write(b"s")
    biofeedback.trigger_ts.append(time.time())
    while biofeedback.recording:
        last = time.time()
        while time.time() - last < 10:
            if keyboard.is_pressed("q"):
                biofeedback.audio_on = False
                biofeedback.recording = False
                break
            time.sleep(0.1)
        biofeedback.serial.write(b"t")
        biofeedback.trigger_ts.append(time.time())
    biofeedback.serial.write(b"e")
    biofeedback.trigger_ts.append(time.time())
    print("Trigger thread finished")


class Biofeedback:
    """
    TODO docstring
    """

    def __init__(
        self,
        state,
        subject_id,
        block,
        egg_pos,
        egg_freq,
        ecg_poses,
        resp_pos,
        sampling_rate,
        hostname,
        port,
    ):
        """
        TODO docstring
        """
        self.SOUNDSCAPE_DURATION = 120
        self.SOUNDSCAPE_FADE = 5
        self.state = state
        self.subject_id = subject_id
        self.block = block
        self.sampling_rate = sampling_rate
        self.egg_pos = egg_pos
        self.ecg_poses = ecg_poses
        self.resp_pos = resp_pos
        self.egg_freq = egg_freq
        self.audio_on = False
        self.audio_start = 0
        self.recording = True
        self.egg_volume = []
        self.resp_volume = []
        self.gr_ts = []
        self.ecg_ts = []
        self.trigger_ts = []
        self.trigger_thread = Thread(target=trigger_loop, args=(self,))
        self.egg_thread = Thread(target=egg_feedback, args=(self,))
        self.resp_thread = Thread(target=resp_feedback, args=(self,))
        self.ecg_thread = Thread(target=ecg_feedback, args=(self,))
        self.initialise_mock_modulation()
        self.initialise_wav_array()
        self.sound_mod = [0.0, 0.5, 0.0]
        self.ft_resp = Client()
        self.ft_ecg = Client()
        self.ft_egg = Client()
        self.ft_resp.connect(hostname, port)
        self.ft_ecg.connect(hostname, port)
        self.ft_egg.connect(hostname, port)
        self.header_resp = self.ft_resp.getHeader()
        self.header_ecg = self.ft_ecg.getHeader()
        self.header_egg = self.ft_egg.getHeader()
        self.ready = True
        if (
            self.header_resp is None
            or self.header_ecg is None
            or self.header_egg is None
        ):
            print("Connection to FieldTrip buffer failed !")
            self.ready = False
        else:
            print("Connection established with the Fieldtrip buffer")
        try:
            self.serial = serial.Serial("/dev/ttyACM0", 115200)
            print("Connection to Serial port established")
        except:
            print("Connection to Serial port failed !")
            self.ready = False
        if self.ready:
            input("Press enter to start")
            self.launch_biofeedback()

    def initialise_mock_modulation(self):
        """
        TODO docstring
        """
        record_folder = Path(__file__).parent / "../records/"
        file_list = os.listdir(record_folder)
        expected_file = f"mock-modulation_{str(date.today())}_{self.subject_id}.json"
        if expected_file in file_list:
            with open(str(record_folder/expected_file),"r") as file:
                mock_data = json.load(file)
                self.mock_time = mock_data["time"]
                self.mock_egg = mock_data[f"egg_{self.block}"]
                self.mock_resp = mock_data[f"resp_{self.block}"]
                self.mock_ecg = mock_data[f"ecg_{self.block}"]
        else:
            print(f"{expected_file} was not found.")
            #self.ready = False

    def initialise_wav_array(self):
        """
        TODO docstring
        """
        root = Path(__file__).parent / "../soundscapes"
        self.soundscapes_folders = [
            str(root / folder)
            for folder in os.listdir(str(root))
            if os.path.isdir(str(root / folder))
        ]
        random.shuffle(self.soundscapes_folders)

        self.egg_wavs = [
            wave.open(folder + "/egg.wav", "rb") for folder in self.soundscapes_folders
        ]
        self.ecg_wavs = [wave.open(
            str(Path(__file__).parent / "../tests_sounds/silence.wav"), "rb"
        ),wave.open(
            str(Path(__file__).parent / "../tests_sounds/silence.wav"), "rb"
        )]
        self.ecg_index = 0
        self.resp_wavs = [
            wave.open(folder + "/resp.wav", "rb") for folder in self.soundscapes_folders
        ]

    def get_audio_volume(self, index):
        """
        TODO docstring
        """
        sc_dur = self.SOUNDSCAPE_DURATION
        fd_dur = self.SOUNDSCAPE_FADE
        t_point = time.time() - self.audio_start
        if t_point < (sc_dur * len(self.soundscapes_folders)):
            if (
                index * sc_dur + fd_dur <= t_point
                and t_point <= (index + 1) * sc_dur - fd_dur
            ):
                return 1.0
            if (index + 1) * sc_dur - fd_dur < t_point and t_point <= (
                index + 1
            ) * sc_dur + fd_dur:
                return 1 - ((t_point - ((index + 1) * sc_dur - fd_dur)) / (fd_dur * 2))
            if index * sc_dur - fd_dur <= t_point and t_point < index * sc_dur + fd_dur:
                return (t_point - (index * sc_dur - fd_dur)) / (fd_dur * 2)
            return 0.0
        self.audio_on = False
        self.recording = False
        return 0.0

    def get_audio_data(self, wav_array):
        """
        TODO docstring
        """
        audio_data = np.zeros(2048)
        for i, wav in enumerate(wav_array):
            volume = self.get_audio_volume(i)
            if volume > 0.0:
                data = np.fromstring(wav.readframes(1024), np.int16) * volume
                if len(data) < 2048:
                    data = np.zeros(2048)
                audio_data += data
            else:
                audio_data += np.zeros(2048)
        return audio_data

    def get_audio_ecg(self):
        """
        TODO docstring
        """
        data = np.fromstring(self.ecg_wavs[self.ecg_index].readframes(1024), np.int16)
        if len(data) < 2048:
            data = np.zeros(2048)
        return data

    def get_mixed_audio_data(self):
        """
        TODO docstring
        """
        mod = 1 / 3
        egg_data = self.get_audio_data(self.egg_wavs)
        ecg_data = self.get_audio_ecg()
        resp_data = self.get_audio_data(self.resp_wavs)
        newdata = (
            (egg_data * (0.2 + 0.8 * self.sound_mod[0])) * mod
            + (ecg_data * self.sound_mod[1]) * mod
            + (resp_data * (0.2 + 0.8 * self.sound_mod[2])) * mod
        ).astype(np.int16)
        self.egg_volume.append(self.sound_mod[0])
        self.resp_volume.append(self.sound_mod[2])
        self.gr_ts.append(time.time())
        return newdata.tostring()

    def save(self):
        """
        TODO docstring
        """
        dict_ = {
            "egg_pos": self.egg_pos,
            "soudscapes_order": self.soundscapes_folders,
            'block': self.block,
            "egg_freq": self.egg_freq,
            "ecg_ts": list(np.array(self.ecg_ts, dtype=np.float)),
            "egg_volume": list(np.array(self.egg_volume, dtype=np.float)),
            "resp_volume": list(np.array(self.resp_volume, dtype=np.float)),
            "gr_ts": list(np.array(self.gr_ts, dtype=np.float)),
            "trigger_ts": list(np.array(self.trigger_ts, dtype=np.float)),
        }
        date_string = str(date.today())
        file = str(Path(__file__).parent /
                   f"../records/biofeedback_{self.subject_id}_{date_string}_{self.state}.json")
        with open(file,"w",encoding="utf8",) as file:
            json.dump(dict_, file)
        print("File saved")

    def launch_biofeedback(self):
        """
        TODO docstring
        """
        self.trigger_thread.start()
        self.ecg_thread.start()
        self.resp_thread.start()
        self.egg_thread.start()
        play_wav(self)
        self.save()


@click.command()
@click.option(
    "--state",
    prompt="State",
    type=click.Choice(["egg", "ecg", "resp", "mock"], case_sensitive=False),
)
@click.option("--subject_id", prompt="Subject id")
@click.option("--block", type=int, prompt="Block")
@click.option("--egg_pos", type=int, prompt="Egg pos")
@click.option("--egg_freq", type=float, prompt="Egg peak frequency")
@click.option("--ecg_poss", type=list, prompt="Ecg poss", default=[1, 7])
@click.option("--resp_pos", type=int, prompt="Resp pos", default=8)
@click.option("--sampling_rate", type=int, prompt="Sampling rate", default=2048)
@click.option("--ip_address", type=str, prompt="Fieldtrip ip", default="192.168.1.1")
@click.option("--port", type=int, prompt="Fieldtrip port", default=1972)
def start_biofeedback(
    state,
    subject_id,
    block,
    egg_pos,
    egg_freq,
    ecg_poss,
    resp_pos,
    sampling_rate,
    ip_address,
    port,
):
    """
    TODO docstring
    """
    Biofeedback(
        state,
        subject_id,
        block,
        egg_pos-1,
        egg_freq,
        ecg_poss,
        resp_pos,
        sampling_rate,
        ip_address,
        port,
    )


if __name__ == "__main__":
    start_biofeedback()
