#Script to Parse Nessus XML and return a csv.
#CL 20171215
#Usage: python3 nessus_xml_parse.py
#Script prompts for input and output file names.
#TODO: Change input to API Call
import xml.etree.ElementTree as ET
import csv

infile = input('input xml filename: ')
outfile = input('output csv filename: ')
lst = list()
tree = ET.parse(infile)
root = tree.getroot()
for item in root.iter('ReportHost') :
    props = item.findall('.//tag')
    for tags in props :
        if tags.attrib['name'] == 'os' :
            os = tags.text
    host = {'name' : item.attrib['name'], 'OS' : os, 'Critical' : 0, 'High' : 0, 'Medium' : 0}
    for ri in item.findall('ReportItem') :
        risk_factor = ri.find('risk_factor')
        risk = risk_factor.text
        if risk != 'None' and risk != 'Low' :
            host[risk] = host[risk] + 1
    lst.append(host)
print('Found',len(lst),'hosts...')
#Build Output
with open(outfile, 'w', newline='') as csvfile :
    fieldnames = ['name', 'OS', 'Critical', 'High', 'Medium']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for server in lst :
        writer.writerow(server)
