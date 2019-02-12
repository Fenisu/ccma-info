# -*- coding: utf-8 -*-
import argparse
import bs4
import json
import logging
import requests
import re
import sys
import xmltodict

TMP_FILE = 'ccmainfo.json'

TITLE = "Títol"
PRIMERA_EMISSIO = "Primera emissió"
EMISSIO_ACTUAL = "Emissió actual"
INFO_LINK = "Info"
HQ_VIDEO = "HQ"
MQ_VIDEO = "MQ"
SUBTITLE_1 = "VTT"
SUBTITLE_2 = "XML"


name_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_dadesItem_MP4.jsp?idint="
hq_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_media.jsp?PROFILE=IPTV&FORMAT=MP4GES&ID="
subs1_urlbase = "http://www.tv3.cat/pvideo/media.jsp?media=video&versio=1&profile=pc&broadcast=false&format=dm&idint="
subs2_urlbase = "http://www.tv3.cat/p3ac/p3acOpcions.jsp?idint="

SUPER3_URL = "www.ccma.cat/tv3/super3/"
SUPER3_FILTER = "media-object"
TV3_URL = "www.ccma.cat/tv3/alacarta/"
TV3_FILTER = "F-capsaImatge"

###########
# Logging
logger = logging.getLogger('ccmainfo_main')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
# end internal config
############
capis = []


def cli_parse():
    parser = argparse.ArgumentParser(description='CCMA.cat INFO')
    parser.add_argument('--batch', dest='batch', nargs='?', default=False,
                        help="Executar sense demanar l'URL.")
    parser.add_argument('--debug', dest='verbose', action='store_true',
                        help="Activar la depuració.")
    parser.set_defaults(verbose=False)
    args = parser.parse_args()
    return args


def get_url(args):
    if not args.batch:
        url = input("Escrigui la seva adreça URL: ")
    else:
        url = args.batch
    if url.find(SUPER3_URL) > -1:
        logger.debug("Adreça del SUPER3")
        return url, SUPER3_FILTER
    elif url.find(TV3_URL) > -1:
        logger.debug("Adreça de TV3")
        return url, TV3_FILTER
    else:
        logger.error("Aquesta URL no és compatible.")
        sys.exit(5)


def load_json():
    try:
        json_file = open(TMP_FILE, "r").read()
        j = json.loads(json_file)
        logger.info("Utilitzant l'antiga llista temporal.")
    except:
        logger.info("Creant la nova llista temporal.")
        j = []
    return j


def create_json(jin):
    j = json.loads(json.dumps(jin))
    logger.info("Reescrivint la llista temporal.")
    try:
        with open(TMP_FILE, 'w') as outfile:
            json.dump(j, outfile)
        logger.debug("Reescriptura de la llista temporal completada.")
    except:
        logger.error("No s'ha pogut escriure la llista temporal.")
        sys.exit(1)


def remove_invalid_win_chars(value, deletechars):
    for c in deletechars:
        value = value.replace(c, '')
    return value


def main():
    args = cli_parse()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    url, parse_filter = get_url(args)
    js = load_json()

    html_doc = requests.get(url).text
    soup = bs4.BeautifulSoup(html_doc, 'html.parser')
    logger.info("Analitzant l'URL {}".format(url))
    id_cap = str(re.split("/", url)[-2])
    try:
        capis_meta = soup.find_all('a', class_=parse_filter)
        for capi_meta in capis_meta:
            p = re.compile('/video/([0-9]{7})/$')
            capis.append(p.search(capi_meta['href']).group(1))
    except:
        id_cap = str(re.split("/", url)[-2])
        capis.append(id_cap)

    capis.reverse()
    first_run = True
    new = False
    for capi in capis:
        logger.debug("Aconseguint l'ID:{}".format(capi))
        try:
            html_doc = requests.get(subs1_urlbase + capi).text
            j = json.loads(html_doc)
            show = j['informacio']['programa']
        except:
            logger.error("Alguna cosa ha sortit molt malament, no es pot analitzar el segon nivell d'URL.")
            sys.exit(2)
        txt_file = list()

        if first_run:
            if show not in js:
                logger.debug("No mostrar al fitxer temporal.")
                js.append(show)
                js.append([])
                new = True
            pos = js.index(show) + 1
            first_run = False
        if not new:
            if capi in js[pos]:
                logger.debug("L'episodi ja existeix, saltant-lo...")
                continue
        logger.debug("Aconseguint diverses dades.")
        # HEADER
        try:
            txt_file.append("{} ({})".format(show, j['informacio']['capitol']))
        except KeyError:
            txt_file.append(show)

        # TITLE
        try:
            html_doc = requests.get(name_urlbase + capi).text
            html_doc_dict = xmltodict.parse(html_doc)
            html_doc_dict = json.dumps(html_doc_dict)
            html_doc_json = json.loads(html_doc_dict)
            txt_file.append("{}: {}".format(TITLE, html_doc_json['item']['title']))
        except:
            pass
        # PRIMERA_EMISSIO
        try:
            txt_file.append("{}: {}".format(PRIMERA_EMISSIO, j['informacio']['data_emissio']['text']))
        except:
            pass
        # EMISSIO_ACTUAL
        try:
            txt_file.append("{}: {}".format(EMISSIO_ACTUAL, j['audiencies']['kantarst']['parametres']['ns_st_ddt']))
        except:
            pass
        # INFO
        txt_file.append("{}: {}".format(INFO_LINK, "{}{}".format(name_urlbase, capi)))
        # MQ
        try:
            for x in html_doc_json['item']['videos']['video']:
                try:
                    txt_file.append("{}: {}".format(x['format'], x['file']['#text']))
                except Exception:
                    continue
        except:
            pass
        # HQ
        try:
            for x in j['media']['url']:
                txt_file.append("{}: {}".format(x['label'], x['file']))
        except KeyError:
            pass
        # SUBS1
        try:
            txt_file.append("{}: {}".format(SUBTITLE_1, j['subtitols']['url']))
        except KeyError:
            pass
        # SUBS2
        try:
            html_doc = requests.get(subs2_urlbase + capi).text
            soup = bs4.BeautifulSoup(html_doc, 'html.parser')
            txt_file.append("{}: {}".format(SUBTITLE_2, soup.sub['url']))
        except:
            pass
        txt_file.append("")
        txt_file.append("")
        txt_file.append("")
        try:
            out_name_file = remove_invalid_win_chars(show, '\/:*?"<>|')
            outfile = open('%s.txt' % out_name_file, 'a')
            logger.info("Escrivint a {}".format(out_name_file))
            outfile.write('\n'.join(txt_file))
            outfile.close()
        except:
            logger.error("Error al escriure l'episodi.")
            sys.exit(1)
        js[pos].append(capi)
    create_json(js)


if __name__ == '__main__':
    main()
