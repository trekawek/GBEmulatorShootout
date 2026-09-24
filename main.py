import pyautogui
import requests
import os
import zipfile
import subprocess
import time
import PIL.Image
import PIL.ImageChops
import sys
import argparse
import json
import traceback

import testroms.blargg
import testroms.mooneye
import testroms.acid
import testroms.samesuite
import testroms.ax6
import testroms.daid
import testroms.ashiepaws
import testroms.cpp
import testroms.mealybug
from test import *
from emulators.catalog import matching_emulators
from site_metadata import EMULATORS as SITE_EMULATORS, test_to_metadata


tests = testroms.acid.all + testroms.blargg.all + testroms.daid.all + testroms.ax6.all + testroms.mooneye.all + testroms.samesuite.all + testroms.ashiepaws.all + testroms.cpp.all + testroms.mealybug.all

def checkFilter(input, filter_data):
    if filter_data is None:
        return True
    input = str(input)

    # if there is at least one !QUERY, a value not matching any of the negative
    # querys will be accepted.
    out_filter = False
    for f in filter_data:
        if f.startswith("!"):
            out_filter = True
            if f[1:] in input:
                return False
    if out_filter:
        return True

    # if there are no !QUERY, a value matching any of the querys will be
    # accpeted.
    for f in filter_data:
        if not f.startswith("!"):
            if f in input:
                return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='append', help="Filter for tests with keywords")
    parser.add_argument('--emulator', action='append', help="Filter to test only emulators with keywords")
    parser.add_argument('--model', action='append', help="Filter for tests of given model")
    parser.add_argument('--get-runtime', action='store_true')
    parser.add_argument('--get-startuptime', action='store_true')
    parser.add_argument('--dump-emulators-json', action='store_true')
    parser.add_argument('--dump-tests-json', action='store_true')
    args = parser.parse_args()

    for model in args.model or []:
        if model not in ["DMG", "CGB", "SGB"]:
            print("Model %s is invalid. Only DMG, CGB and SGB are valid models")
            exit(1)

    tests = [
        test
        for test in tests
        if checkFilter(test, args.test) and checkFilter(test.model, args.model)
    ]
    emulator_specs = matching_emulators(args.emulator)

    if args.dump_emulators_json:
        json.dump({
            spec.name: {
                'id': SITE_EMULATORS[spec.name]['id'],
                'file': spec.result_filename,
                'url': spec.url,
                'systems': SITE_EMULATORS[spec.name]['systems'],
            } for spec in emulator_specs
        }, open("emulators.json", "wt"), indent="  ")
    if args.dump_tests_json:
        json.dump([test_to_metadata(test) for test in tests], open("tests.json", "wt"), indent="  ")
    if args.dump_tests_json or args.dump_emulators_json:
        print("%d emulators" % (len(emulator_specs)))
        print("%d tests" % (len(tests)))
        sys.exit()

    emulators = [spec.create() for spec in emulator_specs]

    print("%d emulators" % (len(emulators)))
    print("%d tests" % (len(tests)))

    if args.get_runtime:
        for emulator in emulators:
            emulator.setup()
            for test in tests:
                if not checkFilter(test, args.test):
                    continue
                print("%s: %s: %g seconds" % (emulator, test, emulator.getRunTimeFor(test)))
            emulator.undoSetup()
        sys.exit()

    if args.get_startuptime:
        from util import imageToBase64

        f = open("startuptime.html", "wt")
        f.write("<html><body>\n")
        for emulator in emulators:
            try:
                emulator.setup()
                dmg_start_time, dmg_screenshot = emulator.measureStartupTime(model=DMG)
                gbc_start_time, gbc_screenshot = emulator.measureStartupTime(model=CGB)
                sgb_start_time, sgb_screenshot = emulator.measureStartupTime(model=SGB)
                if dmg_screenshot is not None:
                    print("Startup time: %s = %g (dmg)" % (emulator, dmg_start_time or 0.0))
                    f.write("%s (dmg)<br>\n<img src='data:image/png;base64,%s'><br>\n" % (emulator, imageToBase64(dmg_screenshot)))
                if gbc_screenshot is not None:
                    print("Startup time: %s = %g (gbc)" % (emulator, gbc_start_time or 0.0))
                    f.write("%s (gbc)<br>\n<img src='data:image/png;base64,%s'><br>\n" % (emulator, imageToBase64(gbc_screenshot)))
                if sgb_screenshot is not None:
                    print("Startup time: %s = %g (sgb)" % (emulator, sgb_start_time or 0.0))
                    f.write("%s (sgb)<br>\n<img src='data:image/png;base64,%s'><br>\n" % (emulator, imageToBase64(sgb_screenshot)))
                emulator.undoSetup()
            except Exception as e:
                print(f'Exception while running {emulator}')
                traceback.print_exc()
                f.write("%s: <br>\n<pre>%s</pre>\n<br>\n" % (emulator, traceback.format_exc()))

        f.write("</body></html>")
        sys.exit()

    results = {}
    for emulator in emulators:
        results[emulator] = {}
        try:
            emulator.setup()
        except Exception:
            print(f'Exception while setting up {emulator}')
            traceback.print_exc()
            continue

        for test in tests:
            skip = False
            for feature in test.required_features:
                if feature not in emulator.features:
                    skip = True
                    print("Skipping %s on %s because of missing feature %s" % (test, emulator, feature))
            if not skip:
                try:
                    result = emulator.run(test)
                    if result is not None:
                        results[emulator][test] = result
                except KeyboardInterrupt:
                    exit(0)
                except:
                    print("Emulator %s failed to run properly" % (emulator))
                    traceback.print_exc()
        emulator.undoSetup()
    emulators.sort(key=lambda emulator: len([result[0] for result in results[emulator].values() if result.result != "FAIL"]), reverse=True)

    from util import imageToBase64

    for emulator in emulators:
        def toBase64(data):
            if data is None:
                return ''
            try:
                return imageToBase64(data)
            except:
                print(f'Exception while converting image to base64')
                traceback.print_exc()
                return ''

        data = {
            'emulator': str(emulator),
            'date': time.time(),
            'tests': {
                str(test): {
                    'result': result.result,
                    'startuptime': result.startuptime,
                    'runtime': result.runtime,
                    'screenshot': toBase64(result.screenshot)
                }
                for test, result in results[emulator].items()
            },
        }
        if results[emulator]:
            json.dump(data, open(emulator.getJsonFilename(), "wt"), indent="  ")
