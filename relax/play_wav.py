import time

import pyaudio


def play_wav(biofeedback):
    """
    TODO docstring
    """
    wf_sample = biofeedback.egg_wavs[0]
    p = pyaudio.PyAudio()
    stream = p.open(
        format=p.get_format_from_width(wf_sample.getsampwidth()),
        channels=wf_sample.getnchannels(),
        rate=wf_sample.getframerate(),
        output=True,
    )

    if biofeedback.state == "mock":
        biofeedback.audio_on = True
    while not biofeedback.audio_on:
        time.sleep(0.1)

    biofeedback.audio_start = time.time()
    data = biofeedback.get_mixed_audio_data()

    while biofeedback.audio_on:
        stream.write(data)
        data = biofeedback.get_mixed_audio_data()
    stream.stop_stream()
    stream.close()
    p.terminate()
