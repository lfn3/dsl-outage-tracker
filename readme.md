DSL Outage Notification Tool
============================

So this is a simple [flask] (http://flask.pocoo.org/) app which scans emails from Chorus, stuffs them into a database, and then hopefully lets you know when your customers are offline.

It's scarcely polished at this point, since it's strictly a tool for internal use.

First you'll need python (2.x, since flask doesn't currently support 3.x), and obviously flask. I'd recommend using virtualenv. If you want this slightly automated, you'll also want to add OutageParse.py as a cron job to run every... however often. I set it to every 15 minutes.

You'll need two giant spreadsheets to get it working. If you ask nicely Chorus's "Service Delivery" should be able to provide you with a file similar to the one I've included, entitled tcnzdsldata.csv. If you look at it at present, it has the only used columns with some sample data in them.

The other is internaldsldata, which you'll have to get out of your database somehow. Or if you ask nicely and provide the appropriate info, I might make a database connector for you.

At this stage I'm not planning on working on this a lot, unless this get used a lot. So please, let me know if you do.

Chur,
byAtlas.