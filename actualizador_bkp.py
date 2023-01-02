import os
import urllib.request as request
from zipfile import ZipFile

import sys
import requests


def unzip(source_filename, dest_dir):
    with ZipFile(source_filename) as zf:
        zf.extractall(dest_dir)
        
        
from pathlib import Path

current_files = []
working_dir = Path()
for path in working_dir.glob("**/*.txt"):
    # filenames
    current_files += [path.stem]
    
import datetime
now = datetime.datetime.now()


# Obtaining the data from the URL's
url_front = 'https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/'

## Carpeta donde quedaran los datos
extract_dir = 'microdatos/'

for y in range(now.year - 1, now.year + 1):
    for Q in range(1, 5):
        file_name = 'EPH_usu_'+str(Q)+'_Trim_'+str(y)+'_txt.zip' # Funciona de 2017 en adelante
        full_file = os.path.join(os.getcwd(), extract_dir, file_name)
        print(full_file)

        response = requests.head(url_front + file_name, allow_redirects=True)
        size = response.headers.get('content-length', -1)
        size_MB = int(size) / float(1 << 20)
        
        ## Verificar tamano de la respuesta. Si no es pesada es porque el archivo no esta subido
        print(file_name)
        print('\t{:<40}: {:.2f} MB'.format('FILE SIZE', size_MB))

        # Descargar el rar
        if size_MB > 0.5: # Si el archivo esta subido
            if not os.path.isfile(full_file): # si aun no existe.
                # Si no esta el directorio lo crea
                if not os.path.exists(extract_dir):
                    os.makedirs(extract_dir)

                # Toma data del URL
                request.urlretrieve(url_front + file_name, full_file)

                # Archive(full_file).extractall(extract_dir)
                with ZipFile(full_file, 'r') as zipObj:
                   # Get list of files names in zip
                    listOfiles = zipObj.namelist()
                
                new_files = [Path(file).stem.lower() for file in listOfiles]
                new_files = [file for file in new_files if 'eph' not in file]  # Exclude 'folder' file
                print(new_files)
                
                if all(item in current_files for item in new_files): # If files already present
                    print('A')
                    os.remove(full_file) # Remove the zip
                else: 
                    print('B')
                    unzip(full_file, extract_dir) # Extract
                    
                    ## Move extracted files to their place, and apply lowercase.
#                     extracted_folder = extract_dir + Path(full_file).stem
                    extracted_folder = extract_dir #+ Path(full_file).stem ## Desde 2do T 21 empezaron a guardar archivos sueltos
    
                    for file in os.listdir(extracted_folder):
                        if '.txt' in file:
                            print(file)
                            current_file_name = '/'.join([extracted_folder, file])
                            if 'hogar' in file:
                                dest_dir = extract_dir + '/hogar/'
                            elif 'indiv' in file:
                                dest_dir = extract_dir + '/individual/'

                            new_name = Path(current_file_name).stem.lower() + '.txt'
                            os.rename(current_file_name, os.path.join(dest_dir, new_name))
                            
#                             print('will remove:' +extracted_folder)
                            # print('will remove:' +full_file)

#                             # os.rmdir(extracted_folder) # remove folder ## Desde 2do T 21 empezaron a guardar archivos sueltos
                            # os.remove(full_file) # Remove the zip

