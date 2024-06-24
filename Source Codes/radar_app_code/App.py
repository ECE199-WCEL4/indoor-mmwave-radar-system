'''
Module:         App.py
Author:         JP Coronado
                2020-08281
                BS Electronics Engineering
Course:         ECE 199 Capstone Project
Description:    Main entry point for multi-radar indoor localization system. Constructs the GUI, handles message
                reception from radar devices, and creates live plots of targets.
'''

import tkinter
from tkinter import ttk
from Config import SystemConfig
from Clustering import *
from tkinter import messagebox
from time import sleep
from multiprocessing import Process, Queue
from paho.mqtt import client as mqtt_client
import re
from ast import literal_eval

import matplotlib
from matplotlib.artist import Artist
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.backend_bases import key_press_handler
from matplotlib import pyplot as plt, animation
import numpy as np


# Read configuration file
# *************************************************
cfg = SystemConfig(filename='config.ini')
cfg.read()

# MQTT client configuration
# *************************************************
class MQTTClientHandler:
    def __init__(self):
        self.client = None
        self.tp_proc = None
        self.radar_queues = {}

mch = MQTTClientHandler()

# Queue for points to be plotted
pq = Queue(maxsize=1)

# Callbacks for buttons
# *************************************************
def on_submit():
    config = {k:v.get() for k,v in {
        'brokeraddr': brokeraddr_var,
        'brokerport': brokerport_var,
        'plot_xlims': entry_plotxlims,
        'plot_ylims': entry_plotylims,
        'clusterrad': clusterrad_var,
        'clustersz': clustersz_var,
        **radaren_vars, 
        **radarpos_vars
    }.items()}
    cfg.update_config(**config)
    updated_config = {k:v for k,v in cfg['SystemSettings'].items()}
    print("Config updated:", updated_config)

def on_start(mch):
    mch.radar_queues = {}
    # Get config
    config = {k: v for k,v in cfg['SystemSettings'].items() if k != "default"}

    client_id = f'asdadasdasdsadasda'
    broker_addr = cfg['SystemSettings']['brokeraddr']
    broker_port = int(cfg['SystemSettings']['brokerport'])
    
    # Get topics according to enabled radars
    topics = []

    for i in range(4):
        if config[f'radar{i+1}_en'] == 'True':
            topics.append(f'sys/radar/radar{i+1}/location')
    
    # Create a queue to hold received points under each topic
    mch.radar_queues = {
        k: Queue(maxsize=1) for k in topics
    }

    # Function that constructs the MQTT client object
    def connect_mqtt(broker_addr, broker_port, topics):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print('Connected to MQTT broker.')
            else:
                print(f'Failed to connect, return code {rc}')
        
        # On message callback function
        def on_message(client, userdata, msg):
            payload = msg.payload.decode()
            # Get the radar name from the topic
            radar_name = msg.topic[10:16]
            # print(f'Got data from {radar_name}')
            # Converts point string to 2-tuple array
            points = [tuple(map(int,p.split(" "))) for p in re.findall(r'-?\d+\s+-?\d+', payload) if p != "0 0"]

            # Get the x, y, and angle orientation of associated radar
            radar_data = {k: v for k,v in [(f'{prop}', float(cfg['SystemSettings'][f'{radar_name}_{prop}'])) for prop in ['x', 'y', 'a']]}
            
            # Put radar information + point list into corresponding topic queue
            if mch.radar_queues[msg.topic].empty():
                mch.radar_queues[msg.topic].put(
                    {
                        'radar_data': radar_data,
                        'points': points
                    }
                )
                

        def on_disconnect(client, userdata, rc):
            print("Disconnected from MQTT broker, return code", rc)

        client = mqtt_client.Client(client_id)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(broker_addr, broker_port)
        client.subscribe(list(zip(topics, [1,1,1,1])))

        return client
    
    # Create MQTT client instance and start non-blocking poll loop
    mch.client = connect_mqtt(broker_addr, 1883, topics=topics)
    # print(mch.radar_queues)
    mch.tp_proc = Process(
        target=lambda: transfer_points(mch, pq, 
            clustering_params=(float(cfg['SystemSettings']['clusterrad']), int(cfg['SystemSettings']['clustersz']))
        ), 
        daemon=True
    )
    mch.client.loop_start()
    mch.tp_proc.start()
    # print("Global pq:",pq)

def on_stop(mch):
    mch.client.disconnect()
    mch.tp_proc.terminate()


# TKinter app layout
# *************************************************
# Create root/app
app = tkinter.Tk()
app.title('mmWave Radar Localization System')
app.geometry('1900x800')
app.rowconfigure(0, weight=1)
app.resizable(True, True)
app.rowconfigure(0, weight=1)
app.columnconfigure(0, weight=1)

app.style = ttk.Style()
app.style.theme_use('clam')

# app.wm_protocol('WM_C')

# Create main frame
frame_main = ttk.LabelFrame(master=app, text="mmWave Radar Localization System", border=2)
frame_main.pack(padx=20, pady=20, side='top', fill='both', expand=True)
frame_main.rowconfigure((0,1,2), weight=0)
frame_main.rowconfigure(3, weight=1)
frame_main.columnconfigure(0, weight=3)
frame_main.columnconfigure((1,2), weight=1)

# Broker parameters
# *************************************************************

frame_brokerinfo = ttk.LabelFrame(
    master=frame_main,
    text='MQTT Broker and Plot Settings',
)   
frame_brokerinfo.grid(row=0, column=0, padx=20, pady=20, sticky='new')
frame_brokerinfo.rowconfigure((0,1), weight=0)
frame_brokerinfo.columnconfigure((0,1,2,3,4,5), weight=1)


brokeraddr_var = tkinter.StringVar(value=cfg['SystemSettings']['brokeraddr'])
brokerport_var = tkinter.StringVar(value=cfg['SystemSettings']['brokerport'])

label_brokeraddr = ttk.Label(master=frame_brokerinfo, text='Broker address')
entry_brokeraddr = ttk.Entry(master=frame_brokerinfo, textvariable=brokeraddr_var)
label_brokeraddr.grid(row=0, column=0, sticky='nw')
entry_brokeraddr.grid(row=0, column=1, sticky='ne')

label_brokerport = tkinter.Label(master=frame_brokerinfo, text='Broker port')
entry_brokerport = tkinter.Entry(master=frame_brokerinfo, textvariable=brokerport_var)
label_brokerport.grid(row=1, column=0, sticky='nw')
entry_brokerport.grid(row=1, column=1, sticky='ne')

# Plot parameters
# *************************************************************

xlims_var = tkinter.StringVar(value=cfg['SystemSettings']['plot_xlims'])
ylims_var = tkinter.StringVar(value=cfg['SystemSettings']['plot_xlims'])

label_plotxlims = ttk.Label(master=frame_brokerinfo, text='Plot x lims (xmin, xmax)')
entry_plotxlims = ttk.Entry(master=frame_brokerinfo, textvariable=xlims_var)
label_plotxlims.grid(row=0, column=2, sticky='nw')
entry_plotxlims.grid(row=0, column=3, sticky='ne')

label_plotylims = tkinter.Label(master=frame_brokerinfo, text='Plot y lims (ymin, ymax)')
entry_plotylims = tkinter.Entry(master=frame_brokerinfo, textvariable=ylims_var)
label_plotylims.grid(row=1, column=2, sticky='nw')
entry_plotylims.grid(row=1, column=3, sticky='ne')

# Cluster parameters
# *************************************************************

clusterrad_var = tkinter.StringVar(value=cfg['SystemSettings']['clusterrad'])
clustersz_var = tkinter.IntVar(value=cfg['SystemSettings']['clustersz'])

label_clusterrad = tkinter.Label(master=frame_brokerinfo, text='Cluster radius (mm)')
entry_clusterrad = tkinter.Entry(master=frame_brokerinfo, textvariable=clusterrad_var)
label_clusterrad.grid(row=0, column=4, sticky='nw')
entry_clusterrad.grid(row=0, column=5, sticky='nw')

label_clusersz = tkinter.Label(master=frame_brokerinfo, text='Cluster size')
spinbox_clusersz = tkinter.Spinbox(master=frame_brokerinfo, textvariable=clustersz_var)
label_clusersz.grid(row=1, column=4, sticky='nw')
spinbox_clusersz.grid(row=1, column=5, sticky='nw')

# Radar parameters
# *************************************************************

# Selecting enabled radars
frame_radarinfo = ttk.LabelFrame(
    master=frame_main,
    text='Radars',
)
frame_radarinfo.grid(row=1, column=0, padx=20, pady=20, sticky='new')
frame_radarinfo.rowconfigure((0,1), weight=1)
frame_radarinfo.columnconfigure((0,1,2,3), weight=1)


radaren_vars = {f'radar{i+1}_en': tkinter.BooleanVar(value=cfg['SystemSettings'][f'radar{i+1}_en']) for i in range(4)}
checks_radaren = [ttk.Checkbutton(master=frame_radarinfo, text=f'Radar {i+1} EN', variable=radaren_vars[f'radar{i+1}_en'], onvalue=True, offvalue=False) for i in range(4)]
for i, check in enumerate(checks_radaren):
    check.grid(row=0, column=i)

frames_radarpositions = [ttk.LabelFrame(master=frame_radarinfo, text=f'Radar {i+1}') for i in range(4)]
for frame in frames_radarpositions:
    frame.rowconfigure((0,1,2), weight=1)
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=1)

for i, frame in enumerate(frames_radarpositions):
    frame.grid(row=1, column=i, padx=5, pady=5, sticky='news')

labels_radarpos = [[ttk.Label(master=frame, text=f'Radar {i+1} {prop}') for prop in ['x', 'y', 'angle']] for i, frame in enumerate(frames_radarpositions)]

radarpos_vars = {f'radar{i+1}_{prop}': tkinter.DoubleVar(value=cfg['SystemSettings'][f'radar{i+1}_{prop}']) for i in range(4) for prop in ['x', 'y', 'a']}
entries_radarpos = [[ttk.Entry(master=frame, textvariable=radarpos_vars[f'radar{i+1}_{prop}']) for prop in ['x', 'y', 'a']] for i, frame in enumerate(frames_radarpositions)]

for labelgrp in labels_radarpos:
    for i, label in enumerate(labelgrp):
        label.grid(row=i, column=0)
        
for entrygrp in entries_radarpos:
    for i, entry in enumerate(entrygrp):
        entry.grid(row=i, column=1)

# Canvas Frame and matplotlib
# ***********************************************************************************
frame_canvas = ttk.LabelFrame(master=frame_main, text="Detected Targets")
frame_canvas.grid(row=0, column=1, rowspan=4, columnspan=3, padx=10, pady=10, sticky='news')

plt.rcParams["figure.figsize"] = [10.0, 10.0]
plt.autoscale(False)

fig, ax = plt.subplots()
fig.suptitle('mmWave Radar Target Locations')
ax.autoscale(False)

canvas = FigureCanvasTkAgg(fig, master=frame_canvas)
canvas.draw()

toolbar = NavigationToolbar2Tk(canvas, frame_canvas, pack_toolbar=False)
toolbar.update()

toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

def animate(i):
    if pq.full():
        ax.clear()
        # print(i)
        xmin, xmax = list(literal_eval(cfg['SystemSettings']['plot_xlims']))
        ymin, ymax = list(literal_eval(cfg['SystemSettings']['plot_xlims']))

        ax.set_xlim([xmin, xmax])
        ax.set_ylim([xmin, xmax])

        ax.xaxis.set_ticks(np.arange(xmin, xmax, 500.0))
        ax.yaxis.set_ticks(np.arange(ymin, ymax, 500.0))

        ax.grid()
        ax.set_xlabel('x (mm)')
        ax.set_ylabel('y (mm)')

        x = []
        y = []
        cx = []
        cy = []
        raw_points, centroids = pq.get()

        try:
            x, y = zip(*raw_points)
        except:
            pass

        try:
            cx, cy = zip(*centroids)
        except:
            pass
                
        ax.plot(x, y, marker='o', lw=0, color='lightgray')
        ax.plot(cx, cy, marker='o', lw=0, color='red')

        for (i,j) in zip(cx, cy):
            ax.text(i, j, f'({round(i, 2)}, {round(j, 2)})', fontsize=10)
    else:
        # print('pq empty')
        pass

    
anim = animation.FuncAnimation(fig, animate, cache_frame_data=False, interval=10, blit=False)


# Button Frame
# ***********************************************************************************

frame_btns = ttk.LabelFrame(master=frame_main, text="Controls")
frame_btns.grid(row=2, column=0, padx=10, pady=10, sticky='new')

btn_updatecfg = ttk.Button(
        master=frame_btns, 
        text='Update configuration', 
        command=lambda: on_submit()
    )   
btn_updatecfg.grid(row=0, column=0, padx=20, pady=5)

btn_restartplot = ttk.Button(
        master=frame_btns, 
        text='Restart live plot', 
        command=lambda: on_start(mch)
)
btn_restartplot.grid(row=0, column=1, padx=20, pady=5)

btn_stopplot = ttk.Button(
        master=frame_btns, 
        text='Stop live plot', 
        command=lambda: on_stop(mch)
)
btn_stopplot.grid(row=0, column=2, padx=20, pady=5)

str_debugtxt = tkinter.StringVar(value="")

btn_displaytext = ttk.Button(
    master=frame_btns,
    text="Print debugging text",
    command=lambda: print(str_debugtxt.get())
)
btn_displaytext.grid(row=1, column=0, padx=20, pady=5)

entry_debugtext = tkinter.Entry(master=frame_btns, textvariable=str_debugtxt)
entry_debugtext.grid(row=1, column=1, columnspan=5, sticky='w', padx=20, pady=5)



if __name__ ==  "__main__":
    print("App start.")
    app.mainloop()
