# headliner
Headliner aggregates headlines and their metadata from the home pages of news sites. This data can then be made available through the included API. See the running version [here](https://headliner.cc)!

### Why?
Headliner gathers information on the size and location of each homepage article, as well as on how long those articles are available. This metadata is then made available allowing for a general overview for how news organizations have covered specific topics and potentially for comparison between these sources.

### How?
Headliner utilizes Selenium to scrape the the homepages of each of the sites designated in the system config file and stores this in a Neo4j graph database. That data is then made available through ElasticSearch and a Flask API. A front-end is built in React and is available [here](https://github.com/mwbenowitz/headliner-front)

### What's Next?
Further features are in development including:
- The ability to start an initial search by date/date range
- Functionality to bulk JSON download of records
- Visualizations of term/topic frequency
- Sentiment analysis of headlines
- Websocket implementation to provide better feedback while searches are running

### Questions?
Open an issue for any feature requests or general feedback!
