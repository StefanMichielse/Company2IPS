# Company2IPS
This is a Python project to aid quick scanning of companies

## Function logic
* Get a company name as a parameter to the script
* Using PhantomJS it goes to the following page to do a WHOIS lookup to get the IP ranges for that company: https://apps.db.ripe.net/search/full-text.html
* Based on the start and end IP address it calculates all possible IP addresses for that range
* It loops through that set of IP addresses and in the loop it queries a MongoDB collection which contains all FTP banners: https://scans.io/series/21-ftp-banner_grab-full_ipv4
* If there are any FTP banners found, using PhantomJS it queries filemare.com to see what files are available

## Prerequisites
* PyMongo
* Selenium
* PhantomJS binary in the same directory as the script
* A MongoDB collection containing all the FTP banners

## Usage
You can run the script by doing:
<code>python Company2IPS.py '[Company name]'</code>

In the script itself change some of the variables for your setup, such as:
* Connection string for the MongoDB
* MongoDB database name
* MongoDB collection name
* Nr of threads, adjust this to the number of threads available on you MongoDB machine

## ToDo
* Calculate the IP range better, currently it'll do only the last 3 bytes. So 192.168.0.1-100 works fine but 192.168.0.99-192.168.1.10 does not work
* Also search for Heartbleed vulnerability
* Implement Shodan API (I hope you got many unlocked queries a month)
* Make it run through a web app with pretty results
* Search multiple WHOIS databases
