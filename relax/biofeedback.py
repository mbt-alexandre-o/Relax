"""
This module contains the `Biofeedback` class which is responsible for managing
the biofeedback system. The class connects to the FieldTrip buffer and starts
threads to handle the collection of physiological data, the modulation of the
soundscapes, and the triggering of events.
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
import numpy as np
import serial

from relax.ecg_feedback import ecg_feedback
from relax.egg_feedback import egg_feedback
from relax.FieldTrip import Client
from relax.play_wav import play_wav
from relax.resp_feedback import resp_feedback


def trigger_loop(biofeedback):
    """
    Send trigger to the serial port define in biofeedback as at specific
    interval as well as saving their timestamp inside biofeedback trigger_ts.

    Parameters
    ----------
    biofeedback: Biofeedback
        instance of the current biofeedback
    """
    print("Trigger thread started")
    trigger_delay = [2.5,5,7.5,10,12.5,15]
    n_delay = len(trigger_delay)
    delay_index = 0

    # Start trigger
    biofeedback.serial.write(b"s")
    biofeedback.trigger_ts.append(time.time())
    while biofeedback.recording:
        last = time.time()
        # The function wait to overcome the delay of trigger_delay at the
        # index delay_index modulo the number of delay (cycling).
        while time.time() - last < trigger_delay[delay_index%n_delay]:
            time.sleep(0.1)
        biofeedback.serial.write(b"t")
        biofeedback.trigger_ts.append(time.time())
        # Incressing delay_index to change the delay.
        delay_index+=1
    # End trigger
    biofeedback.serial.write(b"e")
    biofeedback.trigger_ts.append(time.time())
    print("Trigger thread finished")


class Biofeedback:
    """
    Manage and link the diffferent function and variable used to do the
    biofeedback.
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
        Initialise an instance of Biofeedback

        Parameters
        ----------
        state: String [egg,ecg,resp,mock]
            specify wich biological signal will be modulated online.
        subject_id: String
            unique string id of the subject. It should be the same as the one
            used for recording the baseline.
        block: Int
            block number of the current stimulation.
        egg_pos: Int
            index of the egg electrod that will be used to do the sound
            modulation in the fieldtrip config file.
        egg_freq: Float
            peak frequency of previously selected egg electrod.
        ecg_poses: Array of Int of size 2
            index of the two ecg electrods in the fieldtrip config file.
        resp_pos: Int
            index of the resp belt in the fieldtrip config file.
        sampling_rate: Float
            sampling rate of the fieldtrip buffer (after downsampling)
        hostname: String
            IP address of the fieldtrip buffer
        port: Int
            Port number of the fieldtrip buffer
        """

        # Define constants
        self.SOUNDSCAPE_DURATION = 120
        self.SOUNDSCAPE_FADE = 5

        # Set instance variables
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

        # Define some array that will be put in a json file a the end of the
        # biofeedback
        self.egg_volume = []
        self.resp_volume = []
        self.gr_ts = []
        self.ecg_ts = []
        self.trigger_ts = []

        # Initiate the different threads that will be lauch at the start of the
        # biofeedback
        self.trigger_thread = Thread(target=trigger_loop, args=(self,))
        self.egg_thread = Thread(target=egg_feedback, args=(self,))
        self.resp_thread = Thread(target=resp_feedback, args=(self,))
        self.ecg_thread = Thread(target=ecg_feedback, args=(self,))

        # Load mock modulation data (for testing purposes)
        self.initialise_mock_modulation()

        # Load soundscapes and initialize wave arrays
        self.initialise_wav_array()

        # Set sound modulation
        self.sound_mod = [0.0, 0.5, 0.0]

        # Connect to the FieldTrip buffer
        self.ft_resp = Client()
        self.ft_ecg = Client()
        self.ft_egg = Client()
        self.ft_resp.connect(hostname, port)
        self.ft_ecg.connect(hostname, port)
        self.ft_egg.connect(hostname, port)
        # Initialize headers for biofeedback data
        self.header_resp = self.ft_resp.getHeader()
        self.header_ecg = self.ft_ecg.getHeader()
        self.header_egg = self.ft_egg.getHeader()

        # Check if connection to the FieldTrip buffer was successful
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

        # Connect to the serial port
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
        Initializes mock modulation data if it is available.

        The mock modulation data is used for testing purposes, and consists of
        JSON files containing sound modulation for the EGG, respiratory, and ECG
        soundscapes computed with the resting state.
        """

        # Finding the right mock-modulation file
        record_folder = Path(__file__).parent / "../records/"
        file_list = os.listdir(record_folder)
        expected_file = f"mock-modulation_{str(date.today())}_{self.subject_id}.json"

        if expected_file in file_list:
            with open(str(record_folder/expected_file),"r") as file:
                mock_data = json.load(file)
                # mock_time is the time point for every mock modulation
                # look at create_mock_soundscape to know how it has been created
                self.mock_time = mock_data["time"]
                self.mock_egg = mock_data[f"egg_{self.block}"]
                self.mock_resp = mock_data[f"resp_{self.block}"]
                self.mock_ecg = mock_data[f"ecg_{self.block}"]
        else:
            # If the file is not found, print an error message and exit.
            raise FileNotFoundError(f"{expected_file} was not found.")

    def initialise_wav_array(self):
        """
        Initializes audio files for the soundscapes.
        """
        root = Path(__file__).parent / "../soundscapes"
        self.soundscapes_folders = [
            str(root / folder)
            for folder in os.listdir(str(root))
            if os.path.isdir(str(root / folder))
        ]
        # Shuffle the list of soundscapes for random order.
        random.shuffle(self.soundscapes_folders)

        # Open egg and resp audio files for each soundscape.
        self.egg_wavs = [
            wave.open(folder + "/egg.wav", "rb") for folder in self.soundscapes_folders
        ]
        self.resp_wavs = [
            wave.open(folder + "/resp.wav", "rb") for folder in self.soundscapes_folders
        ]
        # For ecg soundscape we initialize with silence because we you use
        # new wav file when a heart beat is detected.
        self.ecg_wavs = [wave.open(
            str(Path(__file__).parent / "../tests_sounds/silence.wav"), "rb"
        ),wave.open(
            str(Path(__file__).parent / "../tests_sounds/silence.wav"), "rb"
        )]
        # In order to minimize the delay between the heart beat and the sound
        # We preload the sound in advance and change wich sound is played by
        # changing the ecg_index.
        self.ecg_index = 0

    def get_sound_volume(self, index):
        """
        This method return the volume of a sound according to its order
        index. This allow to make fade in and fade out transition between the
        different sounds of a layer.

        Parameters
        ----------
        index: Int
            index (and order) of the soundscape accordind to soundscapes_folders

        Returns
        -------
        _: float
            volume of the soundscape at the current time
        """
        # Reformating name
        sc_dur = self.SOUNDSCAPE_DURATION
        fd_dur = self.SOUNDSCAPE_FADE

        # Current time since the start of the sound
        t_point = time.time() - self.audio_start

        # If we are not at the end of the block
        if t_point < (sc_dur * len(self.soundscapes_folders)):
            # Inside the soundscape time limit
            if (
                index * sc_dur + fd_dur <= t_point
                and t_point <= (index + 1) * sc_dur - fd_dur
            ):
                return 1.0
            # Fade out
            if (index + 1) * sc_dur - fd_dur < t_point and t_point <= (
                index + 1
            ) * sc_dur + fd_dur:
                return 1 - ((t_point - ((index + 1) * sc_dur - fd_dur)) / (fd_dur * 2))
            # Fade In
            if index * sc_dur - fd_dur <= t_point and t_point < index * sc_dur + fd_dur:
                return (t_point - (index * sc_dur - fd_dur)) / (fd_dur * 2)
            # Out side the soundscaoe time limit
            return 0.0
        # If the block duration is over we stop the audio and the recording and
        # put the volume to 0
        self.audio_on = False
        self.recording = False
        return 0.0

    def get_layer_data_continuous(self, wav_array):
        """
        Return the audio data (mixed during transition) of a continuous layer
        i.e. resp or egg at the curent time.
        
        Parameters
        ----------
        wav_array: Array of wav
            Array of wav for a layer in the session order

        Returns
        -------
        layer_data: np.array of np.int16 of size 2048
            audio data of the layer at the current time
        """
        layer_data = np.zeros(2048)
        # For every sound of a layer
        for i, wav in enumerate(wav_array):
            volume = self.get_sound_volume(i)
            # If the sound volume isn't null we start reading its wav file
            if volume > 0.0:
                data = np.fromstring(wav.readframes(1024), np.int16) * volume
                # If we reach the end of the wav file we return silence
                # This should not happen has soundscape duration is higher than
                # every wav file duration
                if len(data) < 2048:
                    data = np.zeros(2048)
                # We mix the data
                layer_data += data
        return layer_data

    def get_layer_data_discontinuous(self,wav_array,wav_index):
        """
        Return the audio data (mixed during transition) of a discontinuous layer
        i.e. ecg at the curent time.
        
        Parameters
        ----------
        wav_array: Array of wav
            Array of wav for a layer
        wav_index: Int
            Index of the wav that should be read

        Returns
        -------
        layer_data: np.array of np.int16 of size 2048
            audio data of the layer at the current time
        """
        layer_data = np.fromstring(wav_array[wav_index].readframes(1024), np.int16)
        # If we reach the end of the wav file we return silence
        if len(layer_data) < 2048:
            layer_data = np.zeros(2048)
        return layer_data

    def get_mixed_audio_data(self):
        """
        Return the mixed audio data of the differents layers
        i.e. ecg, egg and resp at the curent time. Also, record the volume of
        the egg and resp layers for offline check.

        Returns
        -------
        audio_data: np.array of np.int16 of size 2048
            audio data of the soundscape at the current time
        """
        # Every layer data should be divided by their number in order to prevent
        # exceeding the max of np.int16
        mod = 1 / 3

        # Get the audio data of every layer
        ecg_data = self.get_layer_data_discontinuous(self.ecg_wavs,self.ecg_index)
        egg_data = self.get_layer_data_continuous(self.egg_wavs)
        resp_data = self.get_layer_data_continuous(self.resp_wavs)

        # Mixing the audio data
        audio_data = (
            (egg_data * (0.2 + 0.8 * self.sound_mod[0])) * mod
            + (ecg_data * self.sound_mod[1]) * mod
            + (resp_data * (0.2 + 0.8 * self.sound_mod[2])) * mod
        ).astype(np.int16)

        # Recording the volume of the continuous layers and their timestamps
        self.egg_volume.append(self.sound_mod[0])
        self.resp_volume.append(self.sound_mod[2])
        self.gr_ts.append(time.time())

        return audio_data.tostring()

    def save(self):
        """
        Save the different information of the biofeedback block.
        """
        # Save the different variable inside a dictionary
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

        # Get the right file name and folder
        date_string = str(date.today())
        file_index = 0
        file = (Path(__file__).parent /
                f"../records/biofeedback_{self.subject_id}_{date_string}"+
                f"_{self.state}.json")
        while file.is_file():
            file_index+=1
            file = (Path(__file__).parent /
                    f"../records/biofeedback_{self.subject_id}_{date_string}"+
                    f"_{self.state}_{file_index}.json")

        # Save the dictionary as a json file
        with open(str(file),"w") as open_file:
            json.dump(dict_, open_file)
        print("File saved")

    def launch_biofeedback(self):
        """
        Function run after the biofeedback instance have been initialize and
        lauch the different threads used to make the biofeedback works.
        """
        self.trigger_thread.start()
        self.ecg_thread.start()
        self.resp_thread.start()
        self.egg_thread.start()
        # Function run on the main thread
        play_wav(self)
        # Save the information at the and of the block
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
@click.option("--ecg_poses", type=list, prompt="Ecg poss", default=[1, 7])
@click.option("--resp_pos", type=int, prompt="Resp pos", default=8)
@click.option("--sampling_rate", type=int, prompt="Sampling rate", default=2048)
@click.option("--hostname", type=str, prompt="Fieldtrip ip", default="192.168.1.1")
@click.option("--port", type=int, prompt="Fieldtrip port", default=1972)
def start_biofeedback(
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
    Function to run a biofeedback block using the GUI of the click library.
    """
    Biofeedback(
        state,
        subject_id,
        block,
        egg_pos-1,
        egg_freq,
        ecg_poses,
        resp_pos,
        sampling_rate,
        hostname,
        port,
    )


if __name__ == "__main__":
    start_biofeedback()
