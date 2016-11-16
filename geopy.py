# -*- coding: utf-8 -*-
# Copyright 2016 Chris Townsend, All rights reserved.
#
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

"""Geocodes data from an Excel file with at least the following columns: State,Street,City,Zip
    Saves results to CSV appended with Lat,Lon,sent address, returned address
    Eventually loaded onto google maps.
"""
import urllib2
import json
import usaddress
import pandas
import collections
import argparse
import sys


def best_street_address(addr):
    """best_street_address parses a US address using usaddress library and returns an street address portion in the best format for calling the google API.
        :param addr: The address string containing at least the street address since that is the target returned.
    """
    return_addr = addr
    parsed_addr = None
    try: #try to use more precise tag method and then fall back on parse if that doesn't work
        parsed_addr = {v: k for k, v in collections.OrderedDict(usaddress.tag(addr)).iteritems()} #for some reason the key:value was reversed so I'm resolving that here
    except:
        try:
            parsed_addr = {v: k for k, v in collections.OrderedDict(usaddress.parse(addr)).iteritems()} #for some reason the key:value was reversed so I'm resolving that here
        except:
            print("Couldn't parse: {a}".format(a=addr), sys.exc_info()[0])

    try:
        if ('AddressNumber' in parsed_addr and 'StreetName' in parsed_addr):
            return_addr = parsed_addr["AddressNumber"] + "+" + parsed_addr["StreetName"] + "+"
            if ('StreetNamePostType' in parsed_addr):
                return_addr = return_addr + parsed_addr["StreetNamePostType"]
    except:
        print("Error trying to reference keys in parsed_addr:", sys.exc_info()[0])

    return return_addr.replace(" ", "+")

def main():
    """main loads the Excel file, iterates over the rows and attempts to geocode, finally saves results to CSV file.
    """

    parser = argparse.ArgumentParser(description='Geocoding against the google API')
    parser.add_argument('-k', '--key', help='The google API key to use.', required=False)
    parser.add_argument('-i', '--input', help='The Excel file you want to process.', required=True)
    parser.add_argument('-o', '--output', help='The CSV file you want the results saved to.', required=True)
    args = parser.parse_args()

    if ('.csv' not in args.input):
        df = pandas.read_excel(args.input)
    else:
        df = pandas.read_csv(args.input)       
    # add new target columns to store results in
    df['NewLat'] = 9.99991
    df['NewLon'] = 9.99991
    df['address_sent'] = 'address sent'
    df['location_type'] = 'unprocessed          '
    df['address_returned'] = 'address returned'

    key = args.key
    if key == None:
        key = ''

    for index, row in df.iterrows():
        try:
            #note: I've omitted state and zip as this was a requirement when I did this: zips change and I'm bounding the search area by state.
            addr_to_submit =  str(best_street_address(row['Street']) + "," + row["City"] ).replace(" ", "+") #trying to give google the format that works best
            df.set_value(index, 'address_sent', addr_to_submit)

            #if you wanted to limit to zip code this first URL would be the one to use
            #url = "https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s&components=postal_code:%s|country:US" % (addr_to_submit, key, row["Zip"])

            #administrative_area - who would have guessed that is State/Province/County/Neighborhood, etc! This wasn't obvious to me in the docs but it was in a Google Python client comment.
            #Now that I know, it makes perfect sense!
            url = "https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s&components=administrative_area:%s|country:US" % (addr_to_submit, key, row["State"])

            response = urllib2.urlopen(url)
            json_string = response.read()
            jdo = json.loads(json_string)

            if (jdo["status"] == 'OK'):
                results = jdo["results"]
                df.set_value(index, 'address_returned', results[0]["formatted_address"])

                geometry = results[0]["geometry"]
                df.set_value(index, 'location_type', geometry["location_type"])

                location = geometry["location"]
                df.set_value(index, 'NewLat', location["lat"])
                df.set_value(index, 'NewLon', location["lng"])

            else:
                df.set_value(index, 'address_returned', '')
                df.set_value(index, 'NewLat', 0)
                df.set_value(index, 'NewLon', 0)

            if (index % 49 == 0):
                print("Done with {x} records.".format(x=index + 1))

        except:
            print("There was a problem with: {address}".format(address=row['Street']), sys.exc_info()[0])

    print("Saving...")
    #Pandas dataframe puked when I did not include the encoding
    df.to_csv(args.output, encoding='utf-8')

if __name__ == "__main__":
    main()
