#!/usr/bin/env python
# coding: utf-8

# In[1]:


### FECHAS DE ACTUALIZACION DE MICRODATOS

## 2021Q3: 12-02-2022 (135 days)

## 2021Q4: 14-05-2022 (134 days)

## 2022Q1: 05-08-2022 (127 days)

## 2022Q2: 05-11-2022 (127 days)


# In[6]:



from itertools import product
from pathlib import Path
import zipfile
import requests

import urllib
import os
import shutil


# In[3]:


from datetime import datetime, timedelta

def generate_quarter_list(num_quarters):
    current_year = datetime.now().year
    current_quarter = (datetime.now().month - 1) // 3 + 1
    quarter_list = [(current_year, current_quarter)]
    while len(quarter_list) < num_quarters:
        current_quarter -= 1
        if current_quarter == 0:
            current_year -= 1
            current_quarter = 4
        quarter_list.append((current_year, current_quarter))
    return quarter_list

# Example usage
print(generate_quarter_list(5))


# In[4]:



# Obtain the data from the URLs
url_front = 'https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/'
extract_dir = Path('microdatos')

# Generate a list of file names to download
file_names = [f"EPH_usu_{Q}_Trim_{y}_txt.zip" for y, Q in generate_quarter_list(5)]
file_names


# In[18]:



# Download and extract the files
for file_name in file_names:
    full_file = extract_dir / file_name
    print(full_file)

    # Open the file and retrieve its size
    with urllib.request.urlopen(url_front + file_name) as response:
        size = int(response.info().get('Content-Length', -1))
        size_MB = size / float(1 << 20)
    
    # Check the size of the response. If it is not large, it means the file is not uploaded
    print(file_name)
    print('\t{:<40}: {:.2f} MB'.format('FILE SIZE', size_MB))

    # Download the zip file
    if size_MB > 0.5:  # If the file is uploaded
        if not full_file.is_file():  # If it doesn't already exist
            # Download the file from the URL
            response = requests.get(url_front + file_name)
            open(full_file, 'wb').write(response.content)

            # Open the zip file
            with zipfile.ZipFile(full_file, 'r') as zip_obj:
                # Extract the files to the extract_dir directory
                zip_obj.extractall(extract_dir)
                
                # Get a list of the extracted file names
                ext_file_names = zip_obj.namelist()
                
                for txt in ext_file_names:
                    # For each of the files (exclude extracted directories)
                    extracted_txt = extract_dir.joinpath(txt)
                    if os.path.isfile(extracted_txt):
                        
                        ## Fix buggy file names
                        if Path(txt).name.endswith('.txt.txt'):
                            name, ext = os.path.splitext(txt) # split the last .txt from the name
                        else:
                            name = txt # it's ok

                        ## Send extracted txt files to their respective folder 
                        
                        if 'hogar' in txt:
                            dest_subdir = extract_dir.joinpath('hogar')
                        elif 'indiv' in txt:
                            dest_subdir = extract_dir.joinpath('individual')

                        shutil.move(extracted_txt, dest_subdir.joinpath(Path(name).name.lower()))


# In[19]:


### Clean by removing all empty folders which are not needed anymore

# Use the `listdir()` function to get a list of all the subdirectories in the parent directory
parent_dir = './microdatos/'
subdirs = [d for d in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, d))]

# Iterate over the subdirectories and check if they are empty
empty_subdirs = []
for subdir in subdirs:
    subdir_path = os.path.join(parent_dir, subdir)
    if not os.listdir(subdir_path):  # The directory is empty if `os.listdir()` returns an empty list
        empty_subdirs.append(subdir_path)
        
        
for dir_ in empty_subdirs: os.rmdir(dir_)


# In[20]:


# # Ejemplo pagina de data que no fue subida
# 'https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_3_Trim_2023_txt.zip'




