import json
import tkinter as tk
from tkinter import *
from tkinter import font
import wave
from tkinter import ttk
from threading import Thread
import numpy
import pyaudio
from time import ctime,time
import random
import os


# List and randomize the order of the sounds
sounds_file = [
    "sounds/mountain/",
    "sounds/beach/",
    "sounds/south/",
    "sounds/river/",
    "sounds/forest/"
]

random.shuffle(sounds_file)

# Define the name for the saved file
start_time = time()
start_ctime = str(ctime()).replace(" ","_").replace(":","-")
saved_json = {}
FullPath= r"results/"+start_ctime+"_RELAX_SoundEvaluation.json"

# Creation of the saved file
def save_json():
    json_object = json.dumps(saved_json, indent = 0)
    if not os.path.exists("results"):
        os.mkdir("results")
    with open(FullPath, "w") as outfile:
        outfile.write(json_object)

# register the langage
saved_json["langage"]="fr"

# Define the read rate
CHUNK = 1024


# General frame to be used at several occasion
## Question with predetermined anwser
class StringQuestion(ttk.Frame):
    def __init__(self, frame, text,values):
        super().__init__(frame)

        label = ttk.Label(self,text=text)
        label.pack()
        self.answer = ttk.Combobox(self)
        self.answer['values'] = values
        self.answer['state'] = 'readonly'
        self.answer.pack()

    def get(self):
        return self.answer.get()

## Question with a number as an anwser
class IntQuestion(ttk.Frame):
    def __init__(self, frame, text,from_,to,set_ = 18):
        super().__init__(frame)

        label = ttk.Label(self,text=text)
        label.pack()
        self.answer = tk.Spinbox(self,from_=from_,to=to,wrap=True)
        self.answer.delete(0,"end")
        self.answer.insert(0,max(from_,set_))
        self.answer.pack()

    def get(self):
        return self.answer.get()
    
## Question requiering a text
class Question(ttk.Frame):

    def __init__(self, frame, text,number_row = 2):
        super().__init__(frame)

        label = ttk.Label(self,anchor=tk.W,text=text)
        label.pack()
        self.answer = tk.Text(self,height=number_row)
        self.answer.pack(expand=True,fill='x')

    def get(self):
        return self.answer.get('1.0','end')

## Create the class for three sliders, used for both the sound evaluation and the sound level
class Eva(ttk.Frame):

    def __init__(self, frame, top_text, left_text, right_text,command_ = None,from_ = 0, to_ = 100, resolution=0.005, set_ = 50):
        super().__init__(frame)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=10)
        self.columnconfigure(2, weight=1)

        top_label = ttk.Label(self,text=top_text,anchor=tk.CENTER)
        top_label.grid(row=0,column=0,sticky=tk.EW,columnspan=3)

        left_label = ttk.Label(self,anchor=tk.W,text=left_text)
        left_label.grid(row=1,column=0,sticky=tk.W)

        right_label = ttk.Label(self,anchor=tk.E,text=right_text)
        right_label.grid(row=1,column=2,sticky=tk.E)

        self.slider = ttk.Scale(self,from_=from_,to=to_,orient='horizontal',command=command_)
        self.slider.set(set_)
        self.slider.grid(row=2,column=0,sticky=tk.EW,columnspan=3)

    def get(self):
        return self.slider.get()

# Frame for the the first windows
class FirstFrame(ttk.Frame):

    def __init__(self, app):
        super().__init__(app)

        self.app = app

        label = ttk.Label(self,anchor=tk.CENTER,text="Merci de votre participation.\n\nVous allez entendre 5 payasages sonores qu'il vous faudra évaluer.")
        label.place(relx = 0.2,rely=0.2,relwidth=0.65,relheight=0.45)

        self.next_button = tk.Button(self,text="Suivant", command=self.stop)
        self.next_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json["sounds_order"]=sounds_file
        saved_json["end_phase_1"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()

# Frame for the questions beforehand (age,gender) 
class InfoFrame(ttk.Frame):

    def __init__(self, app):
        super().__init__(app)

        self.app = app

        label = ttk.Label(self,anchor=tk.CENTER,text="Avant tout, nous avons quelques informations à vous demander.\n\nCe seront les seules données personnelles stockées.")
        label.place(relx = 0.2,rely=0.2,relwidth=0.6,relheight=0.1)

        self.age_question = IntQuestion(self,"Quel age avez vous?",18,99,18)
        self.age_question.place(relx = 0.2,rely=0.4,relwidth=0.6,relheight=0.1)

        self.sex_question = StringQuestion(self,"Quelle est votre genre ?",("Masculin","Feminin","Autre"))
        self.sex_question.place(relx = 0.2,rely=0.5,relwidth=0.6,relheight=0.1)

        self.next_button = tk.Button(self,text="Suivant",command=self.stop)
        self.next_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json["age"]=self.age_question.get()
        saved_json["gender"]=self.sex_question.get()
        saved_json["end_phase_2"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()

# Frame to set the sound volume
class VolumeFrame(ttk.Frame):

    def __init__(self, app,file):
        super().__init__(app)

        self.file = file
        self.thread = Thread(target=self.play_wav)
        self.stop_thread = False
        self.app = app
        self.volume = 0.0

        self.volume_scale = Eva(
            self,
            "Veuillez faire glisser le slider pour regler le son.\n\nLe son doit être confortable tout en étant bien audible.\n\nVous devez entendre des gouttelettes, un ruisseau et du vent dans une cave.\n\nMerci d'attendre au moins 15s après avoir régler le son afin de s'assurer qu'il convienne bien.\n\n",
            "Low",
            "High",
            to_= 1,
            set_= 0,
            resolution=0.005,
            command_=self.update_volume)
        self.volume_scale.place(relx=0.2,rely=0.2,relwidth=0.6)

        self.stop_button = tk.Button(self,text="Commencer le premier payasage",command=self.stop)
        self.stop_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05)

    def update_volume(self,event):
        self.volume = self.volume_scale.get()

    def play_wav(self):

        def get_data(wf,volume):
            data = wf.readframes(CHUNK)
            decodeddata = numpy.fromstring(data, numpy.int16)
            newdata = (decodeddata*0.30*volume).astype(numpy.int16)
            return newdata.tostring()

        wf = wave.open(self.file, 'rb')

        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

        data = get_data(wf,self.volume)

        while data != b'' and not self.stop_thread:
            stream.write(data)
            data = get_data(wf,self.volume)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)
        self.thread.start()

    def stop(self):
        if self.thread.is_alive():
            self.stop_thread = True
            self.thread.join()
        saved_json["volume"]=self.volume
        self.app.volume = self.volume
        saved_json["volume_end"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()

# Frame of the sounds to be evaluated
class SoundFrame(ttk.Frame):

    def __init__(self, app,file):
        super().__init__(app)

        self.file = file
        self.thread = Thread(target=self.play_wav)
        self.app = app

        label = ttk.Label(self,anchor=tk.CENTER,text="Ecoutez ce payasage.\nProfitez en pour vous relaxer.")
        label.place(relx = 0.4,rely=0.4,relwidth=0.2,relheight=0.2)

    def play_wav(self):

        def get_data(wf):
            data = wf.readframes(CHUNK)
            decodeddata = numpy.fromstring(data, numpy.int16)*self.app.volume
            newdata = (decodeddata*1*self.app.volume).astype(numpy.int16)
            return newdata.tostring()

        wf = wave.open(self.file, 'rb')

        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

        data = get_data(wf)

        while data != b'':
            stream.write(data)
            data = get_data(wf)

        stream.stop_stream()
        stream.close()
        p.terminate()
        self.stop()

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)
        self.thread.start()

    def stop(self):
        saved_json[self.file+"_soundscape_end"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()

# Frame for the evaluation itself
class SoundScapeSurveyRatingFrame(ttk.Frame):

    def __init__(self, app, file):
        super().__init__(app)
        next_string = "Next"

        self.app = app
        self.file = file.replace("sounds/","").replace("/","")

        self.appreciation = Eva(self,"Comment évaluez-vous l’aspect plaisant de ce son ?","Déplaisant","Très plaisant")
        self.appreciation.place(relx=0.2,rely=0.15,relwidth=0.6)

        self.relaxation = Eva(self,"Comment évaluez-vous l’aspect relaxant de ce son ? ","Pas du tout relaxant","Très relaxant")
        self.relaxation.place(relx=0.2,rely=0.4,relwidth=0.6)

        self.interest = Eva(self,"Comment évaluez-vous l’aspect intéressant de ce son ?","Ennuyant","Très intéressant")
        self.interest.place(relx=0.2,rely=0.65,relwidth=0.6)

        self.next_button = tk.Button(self,text=next_string,command=self.stop)
        self.next_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json[self.file+"_interest"]=self.interest.get()
        saved_json[self.file+"_relaxation"]=self.relaxation.get()
        saved_json[self.file+"_appreciation"]=self.appreciation.get()
        saved_json[self.file+"_survey_rating_end"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()

# Frame for the evaluation itself
class SoundScapeSurveyQuestionFrame(ttk.Frame):

    def __init__(self, app, file):
        super().__init__(app)

        next_string = "Suivant"

        self.app = app
        self.file = file.replace("sounds/","").replace("/","")

        self.question_1 = Question(self,"Est-ce que le paysage sonore vous a évoqué une image mentale ?\nSi oui, laquelle/lesquelles ?",number_row=5)
        self.question_1.place(relx=0.2,rely=0.15,relwidth=0.6) 

        self.question_2 = Question(self,"Pouvez vous identifier les différents sons composants le paysage sonore ?\nSi oui, lequel/lesquelles ?",number_row=5)
        self.question_2.place(relx=0.2,rely=0.4,relwidth=0.6) 

        self.question_3 = Question(self,"Avez-vous des suggestions pour améliorer la qualité du paysage sonore ?\n(plus plaisant, relaxant, intéressant)",number_row=5)
        self.question_3.place(relx=0.2,rely=0.65,relwidth=0.6) 

        self.next_button = tk.Button(self,text=next_string,command=self.stop)
        self.next_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json[self.file+"_mental_image"]=self.question_1.get()
        saved_json[self.file+"_composition"]=self.question_2.get()
        saved_json[self.file+"_improvement"]=self.question_3.get()
        saved_json[self.file+"_survey_question_end"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()


# Frame for the the balance
class SoundscapeVolumeFrame(ttk.Frame):

    ## initialise the frame , setting volume at 0 for all the sliders 
    def __init__(self, app,dir):
        super().__init__(app)

        self.dir = dir
        self.thread = Thread(target=self.play_wav)
        self.stop_thread = False
        self.app = app
        self.volume_1 = 0.5
        self.volume_2 = 0.5
        self.volume_3 = 0.5
        info = json.load(open(dir+'info_fr.json'))
        
        label = ttk.Label(self,anchor=tk.CENTER,text="Veuillez selectionner le volume de chaque élément.\nVous devez entendre chaque sons distictement et leur volume doit être harmonieux.\n\nNB: Les noms des sons peuvent être différent de ceux que vous avez perçu(e).\nCela n'impact pas le résultat.")
        label.place(relx = 0.2,rely=0.1,relwidth=0.6,relheight=0.2)

        self.volume_scale_1 = Eva(
            self,
            f"Veuillez sélectionner le volume pour le sons suivant : '{info['cardiac']}'.",
            "Low",
            "High",
            to_= 1.0,
            set_= 0.5,
            resolution=0.005,
            command_=self.update_volume)
        self.volume_scale_1.place(relx=0.2,rely=0.4,relwidth=0.6)

        self.volume_scale_2 = Eva(
            self,
            f"Veuillez sélectionner le volume pour le sons suivant : '{info['resp']}'.",
            "Low",
            "High",
            to_= 1.0,
            set_= 0.5,
            resolution=0.005,
            command_=self.update_volume)
        self.volume_scale_2.place(relx=0.2,rely=0.5,relwidth=0.6)

        self.volume_scale_3 = Eva(
            self,
            f"Veuillez sélectionner le volume pour le sons suivant : '{info['gastric']}'.",
            "Low",
            "High",
            to_= 1.0,
            set_= 0.5,
            resolution=0.005,
            command_=self.update_volume)
        self.volume_scale_3.place(relx=0.2,rely=0.6,relwidth=0.6)

        self.stop_button = tk.Button(self,text="Save volume",command=self.stop)
        self.stop_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05)

    def update_volume(self,event):
        self.volume_1 = self.volume_scale_1.get()
        self.volume_2 = self.volume_scale_2.get()
        self.volume_3 = self.volume_scale_3.get()

    def play_wav(self):

        def get_data(wfs):
            data0 = wfs[0].readframes(CHUNK)
            data1 = wfs[1].readframes(CHUNK)
            data2 = wfs[2].readframes(CHUNK)
            decodeddata0 = numpy.fromstring(data0, numpy.int16)
            decodeddata1 = numpy.fromstring(data1, numpy.int16)
            decodeddata2 = numpy.fromstring(data2, numpy.int16)
            newdata = ((
                (decodeddata0*self.volume_1)*0.33+(decodeddata1*self.volume_2)*0.33+(decodeddata2*self.volume_3)*0.33
                )*self.app.volume).astype(numpy.int16)
            return newdata.tostring()

        wf0 = wave.open(self.dir+"ecg.wav", 'rb')
        wf1 = wave.open(self.dir+"resp.wav", 'rb')
        wf2 = wave.open(self.dir+"egg.wav", 'rb')

        wfs = [wf0,wf1,wf2]

        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf0.getsampwidth()),
                    channels=wf0.getnchannels(),
                    rate=wf0.getframerate(),
                    output=True)

        data = get_data(wfs)

        while data != b'' and not self.stop_thread:
            stream.write(data)
            data = get_data(wfs)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)
        self.thread.start()

    def stop(self):
        if self.thread.is_alive():
            self.stop_thread = True
            self.thread.join()
        name = self.dir.replace("sounds/","").replace("/","")+"_"
        saved_json[name+"gastric_volume"]=self.volume_1
        saved_json[name+"resp_volume"]=self.volume_2
        saved_json[name+"cardiac_volume"]=self.volume_3
        saved_json[name+"soundscape_end"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()
        
class IntermediateFrame(ttk.Frame):

    def __init__(self, app):
        super().__init__(app)

        self.app = app

        label = ttk.Label(self,anchor=tk.CENTER,text="Parfait.\n\nLorsque vous êtes prêt pour le prochain paysage sonore, cliquez sur le boutton 'Suivant'.")
        label.place(relx = 0.2,rely=0.2,relwidth=0.65,relheight=0.45)

        self.next_button = tk.Button(self,text="Suivant", command=self.stop)
        self.next_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json["end_intermediate"]=time()-start_time
        save_json()
        self.pack_forget()
        self.app.next_frame()
        
# Frame for the the last window
class LastFrame(ttk.Frame):

    def __init__(self, app):
        super().__init__(app)

        self.app = app

        label = ttk.Label(self,anchor=tk.CENTER,text="L'expérience est terminée.\nMerci de votre aide.")
        label.place(relx = 0.2,rely=0.2,relwidth=0.6,relheight=0.6)

        self.stop_button = tk.Button(self,text="Fin",command=self.stop)
        self.stop_button.place(relx=0.70,rely=0.85,relwidth=0.25,relheight=0.05) 

    def begin(self):
        self.place(x=0,rely=0,relwidth=1.0,relheight=1.0)

    def stop(self):
        saved_json["end"]=time()-start_time
        save_json()
        self.app.destroy()

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        # Window
        width= self.winfo_screenwidth() 
        height= self.winfo_screenheight()
        self.geometry(f'{width}x{height}+{0}+{0}')
        self.title("RELAX sound evaluation")

        # Style
        self.style = ttk.Style(self)
        self.style.theme_use("alt")
        # Sounds
        
        # Changing font-   family, size and weight
        self.NewFont = font.nametofont("TkDefaultFont")
        self.NewFont.configure(family="Lato",size=20)

        self.volume = 0.0

        # Frame

        self.frame_index = 0
        self.frames = [
            FirstFrame(self),
            InfoFrame(self),
            VolumeFrame(self,file = "sounds/example.wav"),

            SoundFrame(self,file = sounds_file[0]+"all.wav"),
            SoundScapeSurveyRatingFrame(self,file = sounds_file[0]),
            SoundScapeSurveyQuestionFrame(self,file = sounds_file[0]),
            SoundscapeVolumeFrame(self,dir = sounds_file[0]),
            
            IntermediateFrame(self),
            
            SoundFrame(self,file = sounds_file[1]+"all.wav"),
            SoundScapeSurveyRatingFrame(self,file = sounds_file[1]),
            SoundScapeSurveyQuestionFrame(self,file = sounds_file[1]),
            SoundscapeVolumeFrame(self,dir = sounds_file[1]),
            
            IntermediateFrame(self),
            
            SoundFrame(self,file = sounds_file[2]+"all.wav"),
            SoundScapeSurveyRatingFrame(self,file = sounds_file[2]),
            SoundScapeSurveyQuestionFrame(self,file = sounds_file[2]),
            SoundscapeVolumeFrame(self,dir = sounds_file[2]),
            
            IntermediateFrame(self),
            
            SoundFrame(self,file = sounds_file[3]+"all.wav"),
            SoundScapeSurveyRatingFrame(self,file = sounds_file[3]),
            SoundScapeSurveyQuestionFrame(self,file = sounds_file[3]),
            SoundscapeVolumeFrame(self,dir = sounds_file[3]),
            
            IntermediateFrame(self),
            
            SoundFrame(self,file = sounds_file[4]+"all.wav"),
            SoundScapeSurveyRatingFrame(self,file = sounds_file[4]),
            SoundScapeSurveyQuestionFrame(self,file = sounds_file[4]),
            SoundscapeVolumeFrame(self,dir = sounds_file[4]),
            
            LastFrame(self)
        ]
        self.frames[0].begin()

    def next_frame(self):
        self.frame_index+=1
        self.frames[self.frame_index].begin()

if __name__ == "__main__":
    app = App()
    app.mainloop()
