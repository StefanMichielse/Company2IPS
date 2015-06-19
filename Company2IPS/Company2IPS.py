import sys
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from pymongo import MongoClient
import thread
from os import listdir
from time import sleep
import time
from netaddr import IPRange
import requests

maxThreads = 24 #Change this for the max threads to the DB
currentThreads = 0

def start_webdriver():
    try:
        print "[+] Starting webdriver..."
        global driver
        dcap = dict(DesiredCapabilities.PHANTOMJS)
        
        #Set a browser user agent so we dont get identified as a crawler
        dcap["phantomjs.page.settings.userAgent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 "
            "(KHTML, like Gecko) Chrome/15.0.87"
        )
        
        #Fetch files in current dir and select phantomjs, so it doesnt matter whether you run this on windows or linux
        phantomjsLoaded = False
        files = listdir('.')
        for file in files:
            if "phantomjs" in file:
                fileName = "./" + file
                #Allow ssl errors just in case oh and dont download the images cuz we cant see em anyways
                driver = webdriver.PhantomJS(fileName,service_args=["--ignore-ssl-errors=true", "--load-images=false"],desired_capabilities=dcap)
                phantomjsLoaded = True
        if phantomjsLoaded == False:
            print "[+] Could not load phantomjs, make sure the binary is in the folder"
            sys.exit(0)

        print "[+] Succesfully started webdriver"

    except:
        print "[+] Got error while starting webdriver: ", sys.exc_info()[0]
        raise
 
def start_mongo():
    try:
        print "[+] Initializing Database Connection..."
        global client
        global db
        client = MongoClient('mongodb://192.168.178.30:27017/')#Enter your mongodb connect details
        db = client['Scans']#We assume the database is called scans and the collection is FTPHeaders
        print "[+] Succesfully created Database Connection"
    except:
        print "[+] Got error while initiating DB connection: ", sys.exc_info()[0]
        raise

def create_array_from_anchor(anchorText):
    if "inetnum" in anchorText:
        #create temp array
        tempArray = []
        #If inetnum get the start and end ip
        firstIP = anchorText.split(" ")[1]
        lastIP = anchorText.split(" ")[3]

        range = IPRange(firstIP, lastIP)

        for ip in range:
            tempArray.append(str(ip))

        return tempArray
    else:
        return 0

def get_ip_ranges(companyName):
    try:
        #Some local vars
        pageUrl = "https://apps.db.ripe.net/search/full-text.html"
        searchBoxId = "home_search:searchform_q"
        searchButtonId = "home_search:doSearch"
        ipArray = []
        #Set the page load timeout to 20 seconds
        driver.set_page_load_timeout(20)
        #Open the search page
        driver.get(pageUrl)
        #Click the advanced search options
        driver.find_element_by_id("home_search:switchMode").click()
        #Select only inetnum
        el = driver.find_element_by_id('home_search:advancedSearch:selectObjectType')
        for option in el.find_elements_by_tag_name('option'):
            if option.text == 'inetnum':
                option.click()
                break
        #Find the search box
        searchBox = driver.find_element_by_id(searchBoxId)
        #Fill in the company name
        searchBox.send_keys(companyName)
        #Find the search button
        searchButton = driver.find_element_by_id(searchButtonId)
        #Click the search button
        searchButton.click()

        ##Now the results page loads

        #Get the results div
        resultsDiv = driver.find_element_by_id("results")
        #Within the results div get all the anchors
        anchors = resultsDiv.find_elements_by_tag_name("a")
        #check how many results we got
        nr_of_anchors = len(anchors)
        if nr_of_anchors > 0:
            print "[+] Got %s results from RIPE, building the ip ranges... (If there are 10 results, it means there are probably multiple pages so this might take a while)" % nr_of_anchors
            #Loop through the anchors
            for anchor in anchors:
                #Store the text as local var
                anchorText = anchor.text
                #Give the anchor text to a different function which will deal with building the ip ranges
                ipArray += create_array_from_anchor(anchorText)
                
            ##Awesome sauce so that was the first page now we go do the next ones
            currentPage = 1
            try:
                while driver.find_element_by_id("resultsView:paginationViewTop:paginationForm:main:after:repeat:0:byIndex"):
                    currentPage = 2
                    #click the next page button
                    driver.find_element_by_id("resultsView:paginationViewTop:paginationForm:main:after:repeat:0:byIndex").click()
                    #Get the results div
                    resultsDiv = driver.find_element_by_id("results")
                    #Within the results div get all the anchors
                    anchors = resultsDiv.find_elements_by_tag_name("a")
                    #Loop through the anchors
                    for anchor in anchors:
                        #Store the text as local var
                        anchorText = anchor.text
                        #Give the anchor text to a different function which will deal with building the ip ranges
                        ipArray += create_array_from_anchor(anchorText)
            except:
                print "[+] In total got %s result pages from RIPE" % currentPage
                pass




            #return the complete array
            return ipArray

        else:
            print "[+] Got 0 results, quitting..."
            return 0

    except:
        print "Got error while doing the search:", sys.exc_info()[0]
        raise

def mongo_FTPsearch_thread(host):
    global resultsCounter
    global currentThreads
    #Define collection for the FTP banners
    collection = db['FTPHeaders']#We assume the collection is FTPHeaders
    #Search in DB, find limit is quicker than find one so we only execute findone if there actually is a result
    foundItem = collection.find({"host": host}).limit(1).count()
    #If result is returned
    if foundItem == 1:
        itemDetails = collection.find_one({"host": host})
        FTPHeaderResults.append(foundItem)
    resultsCounter += 1
    currentThreads -= 1


def mongo_FTPlookup(RIPE_IPs):
    #Create global array for the DB results
    global FTPHeaderResults
    global currentThreads
    FTPHeaderResults = []
    #Get the amount of ips
    nr_of_ips = len(RIPE_IPs)
    print "[+] Starting FTP Banner search for %s IPs at %s" % (nr_of_ips, time.ctime())
    #Start loop through the array op ips returned from ripe
    for RIPE_IP in RIPE_IPs:
        #print "[+] Currently running %s threads of a max %s" % (currentThreads, maxThreads)
        if currentThreads >= maxThreads:
            #print "[+] Reached max threads, waiting till one finishes"
            while currentThreads >= maxThreads:
                sleep(0.5)
            #print "[+] Starting new thread"
            thread.start_new_thread( mongo_FTPsearch_thread, (RIPE_IP, ) )
            currentThreads += 1
        else:
            thread.start_new_thread( mongo_FTPsearch_thread, (RIPE_IP, ) )
            currentThreads += 1

    print "[+] Started all queries, now waiting for results to come in"

def check_filemare():
    #Global results array
    global FilemareResults
    FilemareResults = []
    #Start loop through FTP banner results
    for FTPHeaderResult  in FTPHeaderResults:
        #Some local vars
        pageUrl = "https://apps.db.ripe.net/search/full-text.html"
        searchBoxId = "q"
        searchButtonName = "search"
        #Open the search page
        driver.get(pageUrl)
        #Find the search box
        searchBox = driver.find_element_by_id(searchBoxId)
        #Fill in the company name
        searchBox.send_keys(FTPHeaderResult)
        #Find the search button
        searchButton = driver.find_element_by_name(searchButtonName)
        #Click the search button
        searchButton.click()

        #Get the results div
        resultsDiv = driver.find_element_by_id("preview")
        #Within the results div get all the divs with class item
        items = resultsDiv.find_elements_by_class_name("item")
        #loop through the items
        for item in items:
            #get everything
            imgSrc = item.find_element_by_class_name("icon").get_attribute("src")
            dataType = (imgSrc.split("/")[2]).split(".")[0]
            nr_of_files = (item.find_element_by_class_name("n").text).split(" ")[1]
            size = item.find_element_by_class_name("sz").text
            lastUpdated = item.find_element_by_class_name("t").text
            url = item.find_element_by_tag_name("a").text
            #build temp array
            tempArray = [dataType, nr_of_files, size, lastUpdated, url, FTPHeaderResult]
            FilemareResults.append(tempArray)

def check_shodan():
    #Shodan normally costs credit to query for a host address, but the way they structure their site it makes it possible to do this for free
    #For example /host/[valid IP] gives a HTTP 200 response /host/[invalid IP] gives a 404 so just by loading the page we can check if they have data
    print "[+] Now checking shodan for available data"

    #Lets loop through all the ips we got from ripe
    for IP in RIPE_IPs:
        #build the url
        shodanUrl = "https://www.shodan.io/host/" + IP
        #go to the url
        r = requests.get(shodanUrl)
        #and get the status code
        print shodanUrl
        print r.status_code
        if r.status_code == 200:
            print "[+] we got a match on shodan for ip: " + IP
        #And sleep for as bit so they dont ban us
        time.sleep(2)


def close():
    print "[+] All done, exiting!..."
    driver.quit()
    #sys.exit(0)
    

if __name__ == "__main__":
    #start the webdriver
    start_webdriver()
    #initiate db connection
    start_mongo()
    #temp var for the company name for testing
    companyName = "prepped"
    #Read companyName as argument
    #companyName = sys.argv[1]
    #Crawl ripe for the ip ranges
    print "[+] Initiating search for: %s" % companyName
    RIPE_IPs = get_ip_ranges(companyName)
    #If no results returned the quit
    if RIPE_IPs == 0:
        close()
    print "[+] In total got %s IPs from RIPE" % len(RIPE_IPs)
    #Define the global results counter
    resultsCounter = 0
    #Define target results counter
    targetCounter = len(RIPE_IPs)
    #Start DB FTP search
    mongo_FTPlookup(RIPE_IPs)
    #Wait for thread results
    while resultsCounter != targetCounter:
        pass
    #Check how many results we found
    nr_of_FTP_Banners = len(FTPHeaderResults)
    print "[+] FTP Banner search completed, we found %s results at %s" % (nr_of_FTP_Banners, time.ctime())
    #Now lets check filemare whats on these bitches
    if nr_of_FTP_Banners > 0:
        print "[+] Now checking filemare for files"
        check_filemare()
        print "[+] Got %s results from filemare" % len(FilemareResults)
    else:
        print "[+] No banners found so skipping filemare"

    #Check shodan
    check_shodan()
    close()
            
            
            

