from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
from elasticsearch import Elasticsearch
from datetime import datetime

app = Flask(__name__)
cors = CORS(app)

@app.route("/")
def main():
    jsonResponse = jsonify({
        "name": "Headlinr",
        "description": "This API returns headlines from major news sources so that differences in coverage can be discovered and analyzed"
    })
    return jsonResponse

@app.route("/articles")
def articles():
    conn = sqlite3.connect('../test.db')
    cur = conn.cursor()
    headline = request.args.get('headline')
    es = Elasticsearch()
    articles = es.search(index='articles', body={'query':{'match': {'headline': headline}}, 'size': 500})
    if articles['hits']['total'] == 0:
        nonResponse = jsonify({'message': 'No results found for your search'})
        return nonResponse
    response = {"total": articles['hits']['total'], 'articles': {}}
    for article in articles['hits']['hits']:
        snaps = []
        articleID = article['_source']['sqlID']
        title = article['_source']['headline']
        url = article['_source']['url']
        print title
        avgScore = 0
        instCount = 0
        for instance in cur.execute("SELECT relID, snap, score FROM snap_articles INNER JOIN articles ON articles.id = snap_articles.article WHERE articles.id=?", (articleID,)):
            print instance[0]
            score = instance[2]
            snapUUID = instance[1]
            snapCur = conn.cursor()
            snapCur.execute("SELECT * FROM snapshots WHERE uuid=?", (snapUUID,))
            snapshot = snapCur.fetchone()
            snapTime = datetime.strptime(snapshot[1], "%Y-%m-%dT%H:%M:%S")
            snaps.append((snapTime, score))
            avgScore += score
            instCount += 1
            snapCur.close()
        source = snapshot[3]
        snaps.sort(key=lambda tup:tup[0])
        avgScore = round(avgScore/instCount, 3)
        if source not in response['articles']:
            response['articles'][source] = []
        response['articles'][source].append({"id": articleID, "headline": title, "url": url, "firstSeen": snaps[0][0], "firstScore": round(snaps[0][1], 3), "lastSeen": snaps[-1][0], "lastScore": round(snaps[-1][1], 3), "avgScore": avgScore})

    cur.close()
    return jsonify(response)

if __name__ == "__main__":
    app.run()
