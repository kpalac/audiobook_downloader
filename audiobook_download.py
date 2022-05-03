#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" Script for downloading multiple resources from a WWW page (e.g. chapters of an audiobook) """



import sys
import os
import re
import urllib.request
from random import randint
import music_tag


HELP="""

audiobook_download [options] [URLs|PHRASE]

This script downloads MP3 files from provided URLs. It tags them and creates playlist out of them. 
Useful for downloading audiobook chapters from a WWW page

Options:

    --search [PHRASE]   Search for available audiobooks

    --output_dir        To what location should the files be downloaded?

    --pls               Create playlist file in target directory

    --no_tag            Skip retagging. By default, title tag will be updated with chapter titles to 
                        help dispaying and sorting in media players

    --dry_run           No downloading, only file list and hrefs will be displayed to check
                        if everything is in order (e.g. if REGEX found some valid resource URLs)

    --supported         List supported audiobook providers

    --version           Display version
    --help, -h          Display this message


Dependencies:

    This program uses music_tag library. Install it by typing: pip3 install music_tag



"""



USER_AGENT="Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0"

PROVIDERS = {
'https://fulllengthaudiobooks.com/': {
    'ext':'mp3', 
    'rx_chapters':re.compile(' src="(https://.*?mp3.*?)"'),
    'search':'https://fulllengthaudiobooks.com/?s=%q',
    'rx_slinks':re.compile('<h2 class="entry-title post-title"><a href="(.*?)".*?rel="bookmark">.*?</a></h2>'),
    'rx_stitles':re.compile('<h2 class="entry-title post-title"><a href=".*?".*?rel="bookmark">(.*?)</a></h2>')
    },

'https://librivox.org/': {'ext':'mp3', 
    'rx_chapters':re.compile('<tr>(.*?)</tr>', re.DOTALL),
    'rx_href':re.compile('</td>.*?<td><a href="(.*?\.mp3.*?)" class="chapter-name">', re.DOTALL),
    'rx_title':re.compile('class="chapter-name">(.*?)</a></td>', re.DOTALL),
    'title_from_href':True

    },
'https://goldenaudiobooks.com/': {'copy_from':'https://fulllengthaudiobooks.com/',
'search': 'https://goldenaudiobooks.com/?s=%q',
'rx_slinks':re.compile('<h2 class="entry-title"><a href="(.*?)".*?rel="bookmark">.*?</a></h2>'),
'rx_stitles':re.compile('<h2 class="entry-title"><a href=".*?".*?rel="bookmark">(.*?)</a></h2>')
    },
'https://bookaudiobooks.com/': {'copy_from':'https://fulllengthaudiobooks.com/',
'search': 'https://bookaudiobooks.com/?s=%q',
'rx_slinks':re.compile('<h2 class="entry-title"><a href="(.*?)".*?rel="bookmark">.*?</a></h2>'),
'rx_stitles':re.compile('<h2 class="entry-title"><a href=".*?".*?rel="bookmark">(.*?)</a></h2>')
    },

'https://archive.org': {'ext':'mp3',
    'rx_chapters':re.compile('<div itemprop="(.*?)</div>', re.DOTALL),
    'rx_href':re.compile('<link itemprop="associatedMedia" href="([^<]*?\.mp3)">', re.DOTALL),
    'rx_title':re.compile('content="(.*?)"'),
    'title_from_href':False,
    'search':'https://archive.org/search.php?query=%q&and[]=mediatype%3A%22audio%22&and[]=subject%3A%22audiobook%22',
    'rx_slinks':re.compile('<a href="([^<]*?)" title=".*?".*?data-event-click-tracking="GenericNonCollection|ItemTile">', re.DOTALL),
    'rx_stitles':re.compile('<a href="[^<]*?" title="(.*?)".*?data-event-click-tracking="GenericNonCollection|ItemTile">', re.DOTALL),
    'slinks_prepend': 'https://archive.org'
    }

}




VERSION="1.0.0"




def slist(lst, idx, default):
    """ Safely extract list element or give default """
    try: return lst[idx]
    except (IndexError, TypeError, ValueError, KeyError) as e: return default

def scast(value, target_type, default_value):
    """ Safely cast into a given type or give default value """
    try:
        if value is None: return default_value
        return target_type(value)
    except (ValueError, TypeError): return default_value




def download_html(url:str):
    """ Download main page into str"""
    try:
        req = urllib.request.Request(url, None, {'User-Agent':USER_AGENT})
        response = urllib.request.urlopen(req)
        html = response.read().decode("utf-8")
 
    except (urllib.error.URLError, ValueError, TypeError, OSError) as e:
        print(f"""\nError downloading main page from {url}: {e}""")
        sys.exit(1)

    return html




def prepare_phrase(phrase:str):
    phrase = phrase.replace(' ','+')
    phrase = phrase.replace('/','+')
    return phrase

def search(phrase:str, **kargs):
    """ Search providers for audiobooks and display results """
    phrase = prepare_phrase(phrase)
    results = []
    
    for pr, body in PROVIDERS.items():
        search = body.get('search')
        rx_slinks = body.get('rx_slinks')
        rx_stitles = body.get('rx_stitles')
        prepend = body.get('slinks_prepend','')

        if search is None or rx_slinks is None or rx_stitles is None: continue

        search = search.replace('%q',phrase)
        html = download_html(search)

        links = re.findall(rx_slinks, html)
        titles = re.findall(rx_stitles, html)
 
        for i,l in enumerate(links):
            if l in (None,''): continue
            l = f'{prepend}{l}'
            t = slist(titles, i, '<ERROR>')
            t = re.sub('&#.*?;','',t)
            results.append ( (l, t) )

    if len(results) == 0: print('No matching audiobooks found!')
    else:
        print(f'Found {len(results)} matching audiobooks:\n')
        for r in results:
            print(f'{r[1]}  ---->{r[0]}')

    return results






def create_manifest(url:str):
    """ Create manifest of chapters contained in WWW page at given URL """
    patterns = []
    for pr, body in PROVIDERS.items():
        if body.get('copy_from') is not None:
            body = PROVIDERS.get(body.get('copy_from'))

        if url.startswith(pr): patterns.append(body)
    
    if patterns == []:
        print("Provider not supported. Aborting...")
        sys.exit(1)

    html = download_html(url)


    manifest = {}
    i = 0
    for p in patterns:
        chapters = re.findall(p.get('rx_chapters',''), html)
        
        for ch in chapters:

            if p.get('rx_href','') == '': ch_href = ch
            else: 
                ch_href = slist( re.findall(p.get('rx_href',''), ch), 0, '')
                if ch_href == '': continue


            if p.get('title_from_href',False):
                ch_title = slist( ch_href.split('/'), -1, '')
                ch_title = slist( ch_title.split('.'), 0, '')
            else:
                if p.get('rx_title','') == '': ch_title = ''
                else: ch_title = slist( re.findall(p.get('rx_title',''), ch), 0, '')

            i += 1
            if ch_title == '': 
                    basename = f'Part {str(i).zfill(3)}.{p.get("ext","unknown")}'
                    ch_title = basename
            else: basename = f'{ch_title} ({str(i).zfill(3)}).{p.get("ext","unknown")}'

            manifest[basename] = { 'href': ch_href, 'title': ch_title }

    return manifest







def download_ress(manifest:dict, output_dir:str, **kargs):
    """ Download and save chapters from manifest """
    dry_run = kargs.get('dry_run', False)

    if not os.path.isdir(output_dir):
        print("""Target directory does not exist! Aborting...""")
        sys.exit(1)


    for basename, item in manifest.items():
        
        manifest[basename]['downloaded'] = False

        href = item.get('href','')
        if href == '': 
            print(f"""Empty URL for {basename}. Ignoring...""")
            continue

        file = f'{output_dir}/{basename}'
        manifest[basename]['file'] = file

        if dry_run:
            print(f'{file}:  <--- {href}')
            continue

        print(f'\nDownloading: {href}')

        if os.path.isfile(file) or os.path.isdir(file):
            print(f"""File {file} already exists! Ignoring...""")
            continue

        try:
            req = urllib.request.Request(href, None, {'User-Agent':USER_AGENT})
            response = urllib.request.urlopen(req)

            with open(file, 'wb') as f:
                f.write(response.read())

            manifest[basename]['downloaded'] = True
            print('Done...')

        except (urllib.error.URLError, ValueError, TypeError, OSError) as e:
            print(f"""\nError downloading {href}: {e}\n\n""")






def gen_playlist(manifest:dict, output_dir:str, format:str, **kargs):
    """ Generate playlist file """
    dry_run = kargs.get('dry_run',False)

    file = f'{output_dir}/playlist.{format}'

    if format == 'pls':

        pls = f"""[playlist]\n\n"""
        i = 1
        for basename, item in manifest.items():
            item = item.get('title')
            pls = f"""{pls}File{i}={basename}\nTitle{i}={item}\n\n"""
            i += 1

    if os.path.isfile(file) or os.path.isdir(file):
        print(f"""\n\nFile {file} already exists! Ignoring...""")
        return 1

    if dry_run:
        print(f"""Playlist saved to {file}...""")
        return 0

    try:
        with open(file, 'w') as f:
            f.write(pls)
        print(f"""Playlist saved to {file}...""")
    except OSError as e:
        print(f"""\nError wriring to {file}: {e}\n\n""")







def retag(manifest:list, **kargs):
    """ Append chapter names to Title tags """
    for basename, item in manifest.items():
        
        file = item.get('file')

        try:
            f = music_tag.load_file(file)
            title = f['title']
            if item.get('title','') not in scast(title, str, ''): 
                title = f"""{title} {item.get('title','')}"""
                f['title'] = title
                f.save()
                print(f'File {file}: Title tag changed to "{title}"')

        except Exception as e:
            print(f"""\nError tagging {file}: {e}""")







def process(url, **kargs):
    """ Main processing function """
    dry_run = kargs.get('dry_run',False)
    output_dir = kargs.get('output_dir','')
    playlist = kargs.get('playlist',False)
    pl_format = kargs.get('pl_format','pls')
    no_tag = kargs.get('no_tag',False)

    manifest = create_manifest(url)
    download_ress(manifest, output_dir, dry_run=dry_run)
    
    if playlist: gen_playlist(manifest, output_dir, pl_format, dry_run=dry_run)
    if not no_tag and not dry_run: retag(manifest)





def main():

    output_dir = os.getcwd()
    dry_run = False
    playlist = False
    pl_format = None
    no_tag = False

    if len(sys.argv) > 1:

        for i, arg in enumerate(sys.argv):

            if i == 0: continue

            if arg.startswith('--output_dir='): 
                args = arg.split('=',1)
                if len(args) > 1: output_dir = args[1]
                continue


            elif arg == '--version': print(VERSION)
            elif arg in ('--help','-h'): print(HELP)
            elif arg == '--supported':
                for s in PROVIDERS.keys(): print(s)

            elif arg == '--search': 
                phrase = slist(sys.argv, i+1, '')
                if phrase == '':
                    print('No search phrase given!')
                    break
                
                search(phrase)
                break
    

            elif arg == '--dry_run':
                dry_run = True
                continue

            elif arg == '--no_tag':
                no_tag = True
                continue
            
            elif arg == '--pls':
                playlist = True
                pl_format = 'pls'
                continue

            else:
                process(arg, dry_run=dry_run, output_dir=output_dir, playlist=playlist, pl_format=pl_format, no_tag=no_tag)


if __name__ == '__main__':
    main()
