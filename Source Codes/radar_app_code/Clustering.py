'''
Module:         Clustering.py
Author:         JP Coronado
                2020-08281
                BS Electronics Engineering
Course:         ECE 199 Capstone Project
Description:    Defines functions for accepting raw point data from radar devices, transforming points to a single
                coordinate system using the radar positions and orientations, and clustering the points using
                DBSCAN and calculating the centroids of clusters.
'''


import numpy as np
from sklearn import metrics
from sklearn.cluster import DBSCAN
from multiprocessing import Queue
from MQTTClientHandler import MQTTClientHandler
from datetime import datetime

def transfer_points(mch: MQTTClientHandler, pq: Queue, clustering_params: tuple):

    while True:
        ready = True
        radar_queues = mch.radar_queues.values()
        for queue in radar_queues:
            if queue.empty():
                ready = False
                break
        if ready:
            # Get the raw points obtained from radars, and transform them
            # according to source radar's position and orientation
            raw_points = []
            for queue in radar_queues:
                radar_data, points = queue.get().values()
                raw_points.extend(map(
                    lambda p: transform_coords(radar_data['x'], radar_data['y'], radar_data['a'], p[0], p[1]),
                    points
                ))
            # print(raw_points)

            # Now apply clustering to the raw points
            cluster_rad, cluster_sz = clustering_params
            centroids = cluster_centroids(raw_points, cluster_rad, cluster_sz)

            if pq.empty():
                # print('Hellowww')
                pq.put((raw_points, centroids))

                
        

def transform_coords(radar_x, radar_y,radar_th, px, py):
    s, c = np.sin(-np.radians(radar_th)), np.cos(-np.radians(radar_th))
    T = [-radar_x, -radar_y]
    R = np.array([[c,-s],[s,c]])
    pn = np.matmul(np.array([px,py]), R) - T
    return tuple(pn)	

def cluster_centroids(points: list, cluster_rad=250.0, cluster_sz=2):
    centroids = []
    if not points:
        return []
    X = np.array(points)
    db = DBSCAN(eps=cluster_rad, min_samples=cluster_sz).fit(X)
    labels = db.labels_
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    cluster_dict = {i: X[labels==i] for i in range(n_clusters_)}

    for cluster in (cluster_dict.values()):
        x, y = (np.mean(cluster, axis=0))
        centroid = (round(x,2), round(y,2))
        centroids.append(centroid)
    
    c = datetime.now()
    current_time = c.strftime('%H:%M:%S')
    print(f"{current_time} {centroids}")

    return centroids

if __name__ == "__main__":
    point_list = [(-2004.0, 4220.0), (-1165.0, 4167.0), (-2164.0000000000005, 4329.0), (-1783.0000000000002, 4499.0), (-1794.9999999999993, 4835.0), (-2213.9999999999995, 4146.0), (-1630.9999999999998, 4014.0), (-2244.9999999999995, 4586.0)]
    # print(cluster(point_list))
