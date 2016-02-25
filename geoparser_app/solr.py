import os
import urllib2
import requests
import string
import re

from ConfigParser import SafeConfigParser
import khooshe
import traceback
import yaml


conf_parser = SafeConfigParser()
conf_parser.read('config.txt')

SOLR_URL = conf_parser.get('general', 'SOLR_URL')
UPLOADED_FILES_COLLECTION_NAME = conf_parser.get('general', 'UPLOADED_FILES_COLLECTION_NAME')


headers = {"content-type" : "application/json" }
params = {"commit" : "true" }

def check_solr():
    '''
    Check is solr running
    '''
    try:
        respond = urllib2.urlopen(SOLR_URL)
        return True
    except:
        return False


def core_exists(core_name):
    '''
    Check if core alreay created
    '''
    if check_solr():
        try:
            url = "{0}{1}/select?q=*%3A*".format(SOLR_URL, core_name)
            respond = urllib2.urlopen(url)
            return True
        except:
            return False
    else:
        print "Error: Solr has not started."
        return False


def create_core(core_name):
    '''
    If Solr core not created, create one.
    '''
    if core_exists(core_name):
        return True
    elif check_solr():
        try:
            file_dir = os.path.realpath(__file__).split("solr.py")[0]
            command = "{0}/../Solr/solr-5.3.1/bin/solr create_core -c {1}".format(file_dir, core_name)
            os.system(command)
            return True
        except:
            return False
    else:
        print False


def get_all_cores():
    '''
    Return all existing cores
    '''
    try:
        url = "{0}admin/cores?action=STATUS&wt=json".format(SOLR_URL)
        r = requests.get(url, headers=headers)
        response = r.json()
        return response["status"].keys()
    except:
        return None


def get_domains_urls(core):
    '''
    Return list of urls (ids) inside that core
    '''
    try:
        url = "{0}{1}/select?q=*%3A*&fl=id&wt=json&indent=true".format(SOLR_URL, core)
        r = requests.get(url, headers=headers)
        response = r.json()
        return ["{0}".format(each['id']) for each in response["response"]["docs"]]
    except:
        return None


def IndexStatus(step, file_name):
    try:
        url = "{0}{1}/select?q=*%3A*&fq=id%3A+%22{2}%22&fl={3}&wt=json&indent=true".format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME, file_name, step)
        r = requests.get(url, headers=headers)
        response = r.json()
        return response['response']['docs'][0][step][0]
    except Exception as e:
        return "none"


def IndexFile(core_name, file_name):
    '''
    Index filename, text, location and points fields in Solr if not already exists.
    '''
    if create_core(core_name):
        try:
            url = "{0}{1}/select?q=*%3A*&fl=id&wt=json&indent=true".format(SOLR_URL, core_name)
            response = urllib2.urlopen(url)
            files = eval(response.read())['response']['docs']
            files = [f['id'] for f in files]
            if file_name in files:
                return True
            else:
                try:
                    if core_name == UPLOADED_FILES_COLLECTION_NAME:
                        payload = {
                            "add":{
                                "doc":{
                                    "id" : str(file_name) ,
                                    "text" : "none",
                                    "locations" : "none",
                                    "points" : "none"
                                }
                            }
                        }
                        r = requests.post("{0}{1}/update".format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME), data=str(payload), params=params,  headers=headers)
                    return True
                except:
                    print "Cannot index status fields"
                    return False
        except:
            print "Error calling solr"
            return False
    else:
        return False


def IndexUploadedFilesText(file_name, text):
    '''
    Index extracted text for given file.
    '''
    text = text.replace("'", " ")
    text = text.rstrip('\n')
    text = text.rstrip()#replace("\n", "")
    file_dir = os.path.realpath(__file__).split("solr.py")[0]
    tmp_json = "{0}static/json/tmp.json".format(file_dir)
    with open(tmp_json, 'w') as f:
        f.write("[{{'id':'{0}', 'text':'{1}', 'locations':'\"none\"', 'points':'\"none\"'}}]".format(file_name, text.encode('ascii', 'ignore')))
        f.close()
    if create_core(UPLOADED_FILES_COLLECTION_NAME):
        try:
            command = "{0}../Solr/solr-5.3.1/bin/post -c {1} {2}".format(file_dir, UPLOADED_FILES_COLLECTION_NAME, tmp_json)
            os.system(command)
            os.remove(tmp_json)
            return (True, "Text indexed to Solr successfully.")
        except:
            return (False, "Cannot index text to Solr.")
    else:
        return (False, "Either Solr not running or cannot create Core.")


def QueryText(file_name):
    '''
    Return extracted and indexed text for each file.
    '''
    if create_core(UPLOADED_FILES_COLLECTION_NAME):
        try:
            url = '{0}{1}/select?q=*%3A*&fq=id%3A%22{2}%22&wt=json&indent=true'.format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME, file_name)
            response = urllib2.urlopen(url)
            return eval(response.read())['response']['docs'][0]['text'][0]
        except:
            return False


def IndexLocationName(name, locations):
    '''
    Index location name for each file.
    '''
    if create_core(UPLOADED_FILES_COLLECTION_NAME):
        try:
            payload = {
                "add":{
                    "doc":{
                        "id" : str(name) ,
                        "locations" : {"set" : "{0}".format(locations)}
                    }
                }
            }
            r = requests.post("{0}{1}/update".format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME), data=str(payload), params=params,  headers=headers)
            return (True, "Location name/s indexed to Solr successfully.")
        except:
            return (False, "Cannot index location name/s to Solr.")
    else:
        return (False, "Either Solr not running or cannot create Core.")


def QueryLocationName(file_name):
    '''
    Return location names for given filename
    '''
    if create_core(UPLOADED_FILES_COLLECTION_NAME):
        try:
            url = '{0}{1}/select?q=*%3A*&fq=id%3A%22{2}%22&wt=json&indent=true'.format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME, file_name)
            response = urllib2.urlopen(url)
            return eval(response.read())['response']['docs'][0]['locations'][0]
        except:
            return False


def IndexLatLon(file_name, points):
    '''
    Index points for given file
    '''
    if create_core(UPLOADED_FILES_COLLECTION_NAME):
        try:
            payload = {
                "add":{
                    "doc":{
                        "id" : str(file_name) ,
                        "points" : {"set" : "{0}".format(points)}
                    }
                }
            }
            r = requests.post("{0}{1}/update".format(SOLR_URL, UPLOADED_FILES_COLLECTION_NAME), data=str(payload), params=params,  headers=headers)
            return (True, "Latitude and longitude indexed to Solr successfully.")
        except:
            return (False, "Cannot index latitude and longitude to Solr.")
    else:
        return (False, "Either Solr not running or cannot create Core.")


def QueryPoints(file_name, core_name):
    '''
    Return geopoints for given filename
    '''
    rows_processed = 0
    total_docs = 0
    if create_core(core_name):
        try:
            url = '{0}{1}/select?q=*%3A*&fq=id%3A%22{2}%22&wt=json'.format(SOLR_URL, core_name, file_name)
            response = requests.get(url)
            response = response.json()
            points = response['response']['docs'][0]['points']
            if 'total_docs' in response['response']['docs'][0]:
                total_docs = response['response']['docs'][0]['total_docs'][0]
                rows_processed = response['response']['docs'][0]['rows_processed'][0]
            listNew = []
            for point in points:
                #listNew += eval(point)
                all_x = re.compile("'x': '([-+]?\d+\.*\d*)").findall(point)
                all_y = re.compile("'y': '([-+]?\d+\.*\d*)").findall(point)
                loc_name = re.compile("'loc_name': '(\w+)").findall(point)
                for i in range(len(all_x)):
                    listNew.append({"loc_name":loc_name[i],"x":all_x[i].encode(), "y":all_y[i].encode()})
            return listNew, total_docs, rows_processed
        except Exception as e:
            print e
            return False


def IndexCrawledPoints(core_name, docs):
    '''
    Index geopoints extracted from crawled data
    '''
    try:
        payload =  []
        for key in docs.keys():
            payload.append({"id":key,
                             "points":"{0}".format(docs[key])
                             })
        r = requests.post("{0}{1}/update".format(SOLR_URL, core_name), data=str(payload), params=params,  headers=headers)
        print r.text
        return (True, "Crawled data geopoints indexed to Solr successfully.")
    except Exception as e:
        print traceback.format_exc()
        print e
        return (False, "Cannot index geopoints from crawled data to Solr.")

def GetIndexSize(core_name):
    
    url = '{0}{1}/select?q=*&wt=json&rows=1'.format(SOLR_URL, core_name)
    
    rows_processed = requests.get(url, headers=headers).json()['response']['numFound']
    return rows_processed
    
            
def QueryPointsIndex(core_name):
    '''
    Return geopoints for given index
    '''
    if create_core(core_name):
        listNew = []
        try:
            # loop for all solr docs using numFound 
            start = 0
            rows = 50000
            while(True):
                url = '{0}{1}/select?q=*&fl=points&wt=json&start={2}&rows={3}'.format(SOLR_URL, core_name, start, rows)
                print url
                start += rows
                response = requests.get(url)
                response = yaml.safe_load(response.text)
                
                # loop ends when all docs are processed
                if len(response['response']['docs']) == 0:
                    break
                
                points = [d['points'][0] for d in response['response']['docs']]
                
                for point_t in points:
                    # below is done to handle character in other encodings
                    # it's a temporary hack we need to handle it better
                    point = point_t.decode('string_escape').decode("ascii", "ignore").encode("ascii")
    
                    all_x = re.compile("'x': '([-+]?\d+\.*\d*)").findall(point)
                    all_y = re.compile("'y': '([-+]?\d+\.*\d*)").findall(point)
                    loc_name = re.compile("'loc_name': '(\w+)").findall(point)
                    
                    if(len(all_x) == len(all_y) == len(loc_name)):
                        #if length of all_x,all_y,loc_name is not same our results are inconsistent
                        for i in range(len(all_x)):
                            listNew.append({"loc_name":loc_name[i], "x":all_x[i].encode(), "y":all_y[i].encode()})
                    else:
                        print "length of all_x,all_y,loc_name is not same"
                        print point
        
            return listNew
        except Exception as e:
            print traceback.format_exc()
            print e
            return listNew
        
def GenerateKhooshe(core_name):
    '''
    Generate Khooshe tiles for given core
    '''
    try:
        all_points = []
        points = QueryPointsIndex(core_name)

        for point in points:
            x = float(point["x"])
            y = float(point["y"])
            all_points.append([x, y])
        exclude = set(string.punctuation)
        file_name = ''.join(ch for ch in core_name if ch not in exclude)

        if len(all_points) > 0:
            khooshe.run_khooshe(all_points, None, "geoparser_app/static/tiles/{0}".format(file_name))
            
        print "Tiles created for {0} Points".format(len(points))
        return len(all_points)
    except Exception as e:
        print traceback.format_exc()
        print e
        print "Unable to generate Khooshe tiles for given core"
    return 0



