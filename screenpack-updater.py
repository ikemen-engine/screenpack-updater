#!/usr/bin/env python3
"""
screenpack-updater.py

Usage:
./screenpack-updater.py <path>

This Python script reads an INI file, parses each line, and applies:

1) key-deletion rules (keys_to_delete),
2) value-modification rules (value_modifications),
3) existing key-transformation rules (transformations),
4) append-if-missing rules (append_if_missing).

If a key matches an entry in keys_to_delete, the line is removed entirely.
If a key matches a rule in value_modifications, its value is updated accordingly.
Then the (possibly modified) key and value are passed through the transformations.

Additionally, all double-quote characters (") are automatically removed from values.
"""

import sys
import re
import argparse
import io
import shutil

append_if_missing = {
    "option info": {"keymenu.menu.pos": "0, 0"},
}

keys_to_delete = {
    "victory screen": [
        re.compile(r"^winquote\.time$", re.IGNORECASE),
    ],
    "attract mode": [
        re.compile(r"^credits\.key$", re.IGNORECASE),
        re.compile(r"^options\.key$", re.IGNORECASE),
    ],
    "hiscore info": [
        re.compile(r"^item\.rank\.active2\.scale$", re.IGNORECASE),
        re.compile(r"^item\.rank\.active\.scale$", re.IGNORECASE),
        re.compile(r"^item\.data\.active2\.scale$", re.IGNORECASE),
        re.compile(r"^item\.data\.active\.scale$", re.IGNORECASE),
        re.compile(r"^item\.name\.active2\.scale$", re.IGNORECASE),
        re.compile(r"^item\.name\.active\.scale$", re.IGNORECASE),
    ],
    "select info": [
        re.compile(r"^stage\.active2\.(?:offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE),
        re.compile(r"^stage\.done\.(?:offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE),
    ],
    "option info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
        re.compile(r"^keymenu\.itemname\.playerno$", re.IGNORECASE),
    ],
    "replay info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
    "menu info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
    "training info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
}

value_modifications = {
    "victory screen": [
        (re.compile(r"^winquote\.spacing$", re.IGNORECASE), re.compile(r"^([^,]*),([^,]*)$"), r"\2"),
    ],
    "dialogue info": [
        (re.compile(r"^p[12]\.text\.spacing$", re.IGNORECASE), re.compile(r"^([^,]*),([^,]*)$"), r"\2"),
    ],
    "hiscore info": [
        (re.compile(r"^item\.result\.text\.win$", re.IGNORECASE), re.compile(r"%s"), "%d"),
        (re.compile(r"^item\.rank\.text\.default$", re.IGNORECASE), re.compile(r"%s"), "%d"),
        (re.compile(r"^item\.rank\.text\.[0-9]+$", re.IGNORECASE), re.compile(r"%s"), "%d"),
    ],
}

transformations = {
    "music": [
        (re.compile(r"^continue\.end\.(.+)$", re.IGNORECASE), ["continueend.\\1"]),
        (re.compile(r"^results\.lose\.(.+)$", re.IGNORECASE), ["resultslose.\\1"]),
    ],
    "title info": [
        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),

        (re.compile(r"^menu\.accept\.key$", re.IGNORECASE), ["menu.done.key"]),

        (re.compile(r"^footer1\.offset$", re.IGNORECASE), ["footer.footer1.offset"]),
        (re.compile(r"^footer1\.font$", re.IGNORECASE), ["footer.footer1.font"]),
        (re.compile(r"^footer1\.scale$", re.IGNORECASE), ["footer.footer1.scale"]),
        (re.compile(r"^footer1\.text$", re.IGNORECASE), ["footer.footer1.text"]),

        (re.compile(r"^footer2\.offset$", re.IGNORECASE), ["footer.footer1.offset"]),
        (re.compile(r"^footer2\.font$", re.IGNORECASE), ["footer.footer1.font"]),
        (re.compile(r"^footer2\.scale$", re.IGNORECASE), ["footer.footer1.scale"]),
        (re.compile(r"^footer2\.text$", re.IGNORECASE), ["footer.footer1.text"]),

        (re.compile(r"^footer3\.offset$", re.IGNORECASE), ["footer.footer1.offset"]),
        (re.compile(r"^footer3\.font$", re.IGNORECASE), ["footer.footer1.font"]),
        (re.compile(r"^footer3\.scale$", re.IGNORECASE), ["footer.footer1.scale"]),
        (re.compile(r"^footer3\.text$", re.IGNORECASE), ["footer.footer1.text"]),

        (re.compile(r"^connecting\.offset$", re.IGNORECASE), ["connecting.host.offset", "connecting.join.offset"]),
        (re.compile(r"^connecting\.font$", re.IGNORECASE), ["connecting.host.font", "connecting.join.font"]),
        (re.compile(r"^connecting\.scale$", re.IGNORECASE), ["connecting.host.scale", "connecting.join.scale"]),

        (re.compile(r"^textinput\.([^\.]+)\.text$", re.IGNORECASE), ["textinput.text.\\1"]),
    ],
    "select info": [
        # cell.* and cursor.* remap (and 1-based -> 0-based) is handled in apply_key_transformations()
        #(re.compile(r"^cell\.([0-9]+)\.([0-9]+)\.offset$", re.IGNORECASE), ["cell.\\1-\\2.offset"]),
        #(re.compile(r"^cell\.([0-9]+)\.([0-9]+)\.facing$", re.IGNORECASE), ["cell.\\1-\\2.facing"]),
        #(re.compile(r"^cell\.([0-9]+)\.([0-9]+)\.skip$", re.IGNORECASE), ["cell.\\1-\\2.skip"]),
        #(re.compile(r"^p([12])\.cursor\.active\.([0-9]+)\.([0-9]+)\.anim$", re.IGNORECASE), ["p\\1.cursor.active.\\2-\\3.anim"]),
        #(re.compile(r"^p([12])\.cursor\.active\.([0-9]+)\.([0-9]+)\.spr$", re.IGNORECASE), ["p\\1.cursor.active.\\2-\\3.spr"]),
        #(re.compile(r"^p([12])\.cursor\.active\.([0-9]+)\.([0-9]+)\.offset$", re.IGNORECASE), ["p\\1.cursor.active.\\2-\\3.offset"]),
        #(re.compile(r"^p([12])\.cursor\.active\.([0-9]+)\.([0-9]+)\.facing$", re.IGNORECASE), ["p\\1.cursor.active.\\2-\\3.facing"]),
        #(re.compile(r"^p([12])\.cursor\.active\.([0-9]+)\.([0-9]+)\.scale$", re.IGNORECASE), ["p\\1.cursor.active.\\2-\\3.scale"]),
        #(re.compile(r"^p([12])\.cursor\.done\.([0-9]+)\.([0-9]+)\.anim$", re.IGNORECASE), ["p\\1.cursor.done.\\2-\\3.anim"]),
        #(re.compile(r"^p([12])\.cursor\.done\.([0-9]+)\.([0-9]+)\.spr$", re.IGNORECASE), ["p\\1.cursor.done.\\2-\\3.spr"]),
        #(re.compile(r"^p([12])\.cursor\.done\.([0-9]+)\.([0-9]+)\.offset$", re.IGNORECASE), ["p\\1.cursor.done.\\2-\\3.offset"]),
        #(re.compile(r"^p([12])\.cursor\.done\.([0-9]+)\.([0-9]+)\.facing$", re.IGNORECASE), ["p\\1.cursor.done.\\2-\\3.facing"]),
        #(re.compile(r"^p([12])\.cursor\.done\.([0-9]+)\.([0-9]+)\.scale$", re.IGNORECASE), ["p\\1.cursor.done.\\2-\\3.scale"]),

        (re.compile(r"^p([12])\.teammenu\.accept\.key$", re.IGNORECASE), ["p\\1.teammenu.done.key"]),

        (re.compile(r"^p([12])\.palmenu\.accept\.key$", re.IGNORECASE), ["p\\1.palmenu.done.key"]),

        (re.compile(r"^record\.([^\.]+)\.text$", re.IGNORECASE), ["record.text.\\1"]),
        (re.compile(r"^title\.([^\.]+)\.text$", re.IGNORECASE), ["title.text.\\1"]),

        #(re.compile(r"^p([12])\.palmenu\.random\.text$", re.IGNORECASE), ["p\\1.palmenu.number.text.random"]),

        (re.compile(r"^stage\.active\.font$", re.IGNORECASE), ["stage.font", "stage.active.font"]),
        (re.compile(r"^stage\.active\.(offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["stage.\\1"]),

        (re.compile(r"^p([12])\.face.applypal$", re.IGNORECASE), ["p\\1.face.applypal", "p\\1.face.done.applypal"]),
        (re.compile(r"^p([12])\.face2.applypal$", re.IGNORECASE), ["p\\1.face2.applypal", "p\\1.face2.done.applypal"]),
    ],
    "vs screen": [
        # After global member remap, pX.memberY.key -> pZ.key these should be pZ.select.key instead of plain pZ.key.
        (re.compile(r"^p([1-8])\.key$", re.IGNORECASE), ["p\\1.select.key"]),

        (re.compile(r"^p([12])\.accept\.key$", re.IGNORECASE), ["p\\1.done.key"]),

        (re.compile(r"^p([12])\.applypal$", re.IGNORECASE), ["p\\1.applypal", "p\\1.done.applypal"]),
        (re.compile(r"^p([12])\.face2.applypal$", re.IGNORECASE), ["p\\1.face2.applypal", "p\\1.face2.done.applypal"]),
    ],
    "victory screen": [
        (re.compile(r"^winquote\.spacing$", re.IGNORECASE), ["winquote.textspacing"]),
        (re.compile(r"^winquote\.delay$", re.IGNORECASE), ["winquote.textdelay"]),
    ],
    "option info": [
        (re.compile(r"^menu\.itemname\.menugame\.stunbar$", re.IGNORECASE), ["menu.itemname.menugame.dizzy"]),
        (re.compile(r"^menu\.itemname\.menugame\.guardbar$", re.IGNORECASE), ["menu.itemname.menugame.guardbreak"]),
        (re.compile(r"^menu\.itemname\.menugame\.redlifebar$", re.IGNORECASE), ["menu.itemname.menugame.redlife"]),
        (re.compile(r"^menu\.itemname\.menuvideo\.vretrace$", re.IGNORECASE), ["menu.itemname.menuvideo.vsync"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^keymenu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["keymenu.menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^keymenu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["keymenu.menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^keymenu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["keymenu.menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^keymenu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["keymenu.menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^keymenu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["keymenu.menu.item.active.bg.\\1.scale"]),

        (re.compile(r"^keymenu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["keymenu.menu.item.bg.\\1.anim"]),
        (re.compile(r"^keymenu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["keymenu.menu.item.bg.\\1.spr"]),
        (re.compile(r"^keymenu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["keymenu.menu.item.bg.\\1.offset"]),
        (re.compile(r"^keymenu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["keymenu.menu.item.bg.\\1.facing"]),
        (re.compile(r"^keymenu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["keymenu.menu.item.bg.\\1.scale"]),

        (re.compile(r"^keymenu\.p([12])\.pos$", re.IGNORECASE), ["keymenu.p\\1.menuoffset"]),

        (re.compile(r"^keymenu\.item\.p([12])\.offset$", re.IGNORECASE), ["keymenu.p\\1.playerno.offset"]),
        (re.compile(r"^keymenu\.item\.p([12])\.font$", re.IGNORECASE), ["keymenu.p\\1.playerno.font"]),
        (re.compile(r"^keymenu\.item\.p([12])\.scale$", re.IGNORECASE), ["keymenu.p\\1.playerno.scale"]),

        (re.compile(r"^keymenu\.item\.spacing$", re.IGNORECASE), ["keymenu.menu.item.spacing"]),

        (re.compile(r"^keymenu\.item\.value\.active\.offset$", re.IGNORECASE), ["keymenu.menu.item.value.active.offset"]),
        (re.compile(r"^keymenu\.item\.value\.active\.font$", re.IGNORECASE), ["keymenu.menu.item.value.active.font"]),
        (re.compile(r"^keymenu\.item\.value\.active\.scale$", re.IGNORECASE), ["keymenu.menu.item.value.active.scale"]),

        (re.compile(r"^keymenu\.item\.value\.conflict\.offset$", re.IGNORECASE), ["keymenu.menu.item.value.conflict.offset"]),
        (re.compile(r"^keymenu\.item\.value\.conflict\.font$", re.IGNORECASE), ["keymenu.menu.item.value.conflict.font"]),
        (re.compile(r"^keymenu\.item\.value\.conflict\.scale$", re.IGNORECASE), ["keymenu.menu.item.value.conflict.scale"]),

        (re.compile(r"^keymenu\.item\.value\.offset$", re.IGNORECASE), ["keymenu.menu.item.value.offset"]),
        (re.compile(r"^keymenu\.item\.value\.font$", re.IGNORECASE), ["keymenu.menu.item.value.font"]),
        (re.compile(r"^keymenu\.item\.value\.scale$", re.IGNORECASE), ["keymenu.menu.item.value.scale"]),

        (re.compile(r"^keymenu\.item\.info\.active\.offset$", re.IGNORECASE), ["keymenu.menu.item.info.active.offset"]),
        (re.compile(r"^keymenu\.item\.info\.active\.font$", re.IGNORECASE), ["keymenu.menu.item.info.active.font"]),
        (re.compile(r"^keymenu\.item\.info\.active\.scale$", re.IGNORECASE), ["keymenu.menu.item.info.active.scale"]),

        (re.compile(r"^keymenu\.item\.info\.offset$", re.IGNORECASE), ["keymenu.menu.item.info.offset"]),
        (re.compile(r"^keymenu\.item\.info\.font$", re.IGNORECASE), ["keymenu.menu.item.info.font"]),
        (re.compile(r"^keymenu\.item\.info\.scale$", re.IGNORECASE), ["keymenu.menu.item.info.scale"]),

        (re.compile(r"^keymenu\.boxcursor\.coords$", re.IGNORECASE), ["keymenu.menu.boxcursor.coords"]),
        (re.compile(r"^keymenu\.boxcursor\.visible$", re.IGNORECASE), ["keymenu.menu.boxcursor.visible"]),
        (re.compile(r"^keymenu\.boxcursor\.col$", re.IGNORECASE), ["keymenu.menu.boxcursor.col"]),
        (re.compile(r"^keymenu\.boxcursor\.alpharange$", re.IGNORECASE), ["keymenu.menu.boxcursor.alpharange"]),

        (re.compile(r"^textinput\.([^\.]+)\.text$", re.IGNORECASE), ["textinput.text.\\1"]),
    ],
    "replay info": [
        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),
    ],
    "menu info": [
        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),
    ],
    "training info": [
        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),

        (re.compile(r"^menu\.valuename\.dummycontrol\.cooperative$", re.IGNORECASE), ["menu.valuename.dummycontrol_cooperative"]),
        (re.compile(r"^menu\.valuename\.dummycontrol\.ai$", re.IGNORECASE), ["menu.valuename.dummycontrol_ai"]),
        (re.compile(r"^menu\.valuename\.dummycontrol\.manual$", re.IGNORECASE), ["menu.valuename.dummycontrol_manual"]),

        (re.compile(r"^menu\.valuename\.ailevel\.1$", re.IGNORECASE), ["menu.valuename.ailevel_1"]),
        (re.compile(r"^menu\.valuename\.ailevel\.2$", re.IGNORECASE), ["menu.valuename.ailevel_2"]),
        (re.compile(r"^menu\.valuename\.ailevel\.3$", re.IGNORECASE), ["menu.valuename.ailevel_3"]),
        (re.compile(r"^menu\.valuename\.ailevel\.4$", re.IGNORECASE), ["menu.valuename.ailevel_4"]),
        (re.compile(r"^menu\.valuename\.ailevel\.5$", re.IGNORECASE), ["menu.valuename.ailevel_5"]),
        (re.compile(r"^menu\.valuename\.ailevel\.6$", re.IGNORECASE), ["menu.valuename.ailevel_6"]),
        (re.compile(r"^menu\.valuename\.ailevel\.7$", re.IGNORECASE), ["menu.valuename.ailevel_7"]),
        (re.compile(r"^menu\.valuename\.ailevel\.8$", re.IGNORECASE), ["menu.valuename.ailevel_8"]),

        (re.compile(r"^menu\.valuename\.guardmode\.none$", re.IGNORECASE), ["menu.valuename.guardmode_none"]),
        (re.compile(r"^menu\.valuename\.guardmode\.auto$", re.IGNORECASE), ["menu.valuename.guardmode_auto"]),

        (re.compile(r"^menu\.valuename\.dummymode\.stand$", re.IGNORECASE), ["menu.valuename.dummymode_stand"]),
        (re.compile(r"^menu\.valuename\.dummymode\.crouch$", re.IGNORECASE), ["menu.valuename.dummymode_crouch"]),
        (re.compile(r"^menu\.valuename\.dummymode\.jump$", re.IGNORECASE), ["menu.valuename.dummymode_jump"]),
        (re.compile(r"^menu\.valuename\.dummymode\.wjump$", re.IGNORECASE), ["menu.valuename.dummymode_wjump"]),

        (re.compile(r"^menu\.valuename\.distance\.any$", re.IGNORECASE), ["menu.valuename.distance_any"]),
        (re.compile(r"^menu\.valuename\.distance\.close$", re.IGNORECASE), ["menu.valuename.distance_close"]),
        (re.compile(r"^menu\.valuename\.distance\.medium$", re.IGNORECASE), ["menu.valuename.distance_medium"]),
        (re.compile(r"^menu\.valuename\.distance\.far$", re.IGNORECASE), ["menu.valuename.distance_far"]),

        (re.compile(r"^menu\.valuename\.buttonjam\.none$", re.IGNORECASE), ["menu.valuename.buttonjam_none"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.a$", re.IGNORECASE), ["menu.valuename.buttonjam_a"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.b$", re.IGNORECASE), ["menu.valuename.buttonjam_b"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.c$", re.IGNORECASE), ["menu.valuename.buttonjam_c"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.x$", re.IGNORECASE), ["menu.valuename.buttonjam_x"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.y$", re.IGNORECASE), ["menu.valuename.buttonjam_y"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.z$", re.IGNORECASE), ["menu.valuename.buttonjam_z"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.s$", re.IGNORECASE), ["menu.valuename.buttonjam_s"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.d$", re.IGNORECASE), ["menu.valuename.buttonjam_d"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.w$", re.IGNORECASE), ["menu.valuename.buttonjam_w"]),
    ],
    "attract mode": [
        (re.compile(r"^menu\.bg\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.bg.\\1.scale"]),

        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.anim$", re.IGNORECASE), ["menu.item.active.bg.\\1.anim"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.spr$", re.IGNORECASE), ["menu.item.active.bg.\\1.spr"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.offset$", re.IGNORECASE), ["menu.item.active.bg.\\1.offset"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.facing$", re.IGNORECASE), ["menu.item.active.bg.\\1.facing"]),
        (re.compile(r"^menu\.bg\.active\.([^\.]+)\.scale$", re.IGNORECASE), ["menu.item.active.bg.\\1.scale"]),

        (re.compile(r"^menu\.accept\.key$", re.IGNORECASE), ["menu.done.key"]),
        (re.compile(r"^options\.key$", re.IGNORECASE), ["options.keycode"]),
    ],
    "challenger info": [
        (re.compile(r"^text$", re.IGNORECASE), ["text.text"]),
    ],
    "continue screen": [
        (re.compile(r"^accept\.key$", re.IGNORECASE), ["done.key"]),
    ],
    "dialogue info": [
        (re.compile(r"^p([12])\.text\.spacing$", re.IGNORECASE), ["p\\1.text.textspacing"]),
        (re.compile(r"^p([12])\.text\.delay$", re.IGNORECASE), ["p\\1.text.textdelay"]),
    ],
    "hiscore info": [
        (re.compile(r"^item\.rank\.([0-9]+)\.text$", re.IGNORECASE), ["item.rank.text.\\1"]),
        # Specific rules come first to override the generic rule
        (re.compile(r"^item\.data\.score\.text$", re.IGNORECASE), ["item.result.text.score"]),
        (re.compile(r"^item\.data\.time\.text$", re.IGNORECASE), ["item.result.text.time"]),
        (re.compile(r"^item\.data\.win\.text$", re.IGNORECASE), ["item.result.text.win"]),
        (re.compile(r"^item\.data\.(.+)$", re.IGNORECASE), ["item.result.\\1"]),
        (re.compile(r"^title\.data\.(.+)$", re.IGNORECASE), ["title.result.\\1"]),

        (re.compile(r"^accept\.key$", re.IGNORECASE), ["done.key"]),
    ],
    "warning info": [
        (re.compile(r"^text\.ratio\.text$", re.IGNORECASE), ["text.text.ratio"]),
        (re.compile(r"^text\.reload\.text$", re.IGNORECASE), ["text.text.reload"]),
        (re.compile(r"^text\.noreload\.text$", re.IGNORECASE), ["text.text.noreload"]),
        (re.compile(r"^text\.keys\.text$", re.IGNORECASE), ["text.text.keys"]),
        (re.compile(r"^text\.pad\.text$", re.IGNORECASE), ["text.text.pad"]),
        (re.compile(r"^text\.shaders\.text$", re.IGNORECASE), ["text.text.shaders"]),
    ],
}

SECTION_REGEX = re.compile(r'^[ \t]*\[([^]]+)\][ \t]*(?:;.*)?$')
KEY_VALUE_REGEX = re.compile(r'^[ \t]*(;?)[ \t]*([^=]+)=[ \t]*(.*)$')

def _ensure_utf8_stdio():
    """
    Force UTF-8 output on Windows consoles / redirection to avoid
    UnicodeEncodeError (e.g., when encountering U+FEFF BOM).
    """
    try:
        # Python 3.7+ supports reconfigure on text I/O wrappers.
        sys.stdout.reconfigure(encoding='utf-8', errors='strict')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # If reconfigure isn't available, continue — input handling
        # below still strips a BOM via 'utf-8-sig'.
        pass

def _remap_member_key(orig_key: str):
    """
    Global mapping for any key that starts with p1./p2. and contains a ".memberX"
    segment anywhere in the key path. The mapping is:
      p1.member1 -> p1 (member segment removed)
      p1.member2 -> p3
      p1.member3 -> p5
      p1.member4 -> p7
      p2.member1 -> p2 (member segment removed)
      p2.member2 -> p4
      p2.member3 -> p6
      p2.member4 -> p8

    Examples:
      p1.member3.icon.offset            -> p5.icon.offset
      p1.value.empty.icon.member4.spr   -> p7.value.empty.icon.spr
      p2.member2.icon.spr               -> p4.icon.spr
    """
    m = re.match(r'^(p)([12])(\..*)$', orig_key, flags=re.IGNORECASE)
    if not m:
        return orig_key, False

    p_letter, base_str, rest = m.group(1), m.group(2), m.group(3)
    mm = re.search(r'\.member([1-4])', rest, flags=re.IGNORECASE)
    if not mm:
        return orig_key, False

    base = int(base_str)
    member = int(mm.group(1))
    target_map = {1: [1, 3, 5, 7], 2: [2, 4, 6, 8]}
    new_p = target_map[base][member - 1]
    new_rest = rest[:mm.start()] + rest[mm.end():]  # remove ".memberX" only
    return f"{p_letter}{new_p}{new_rest}", True

def _remap_boxcursor_alpharange(orig_key: str):
    """
    If key name ends with 'boxcursor.alpharange' the mapping changes the key to
    'boxcursor.pulse'. Values set to '30, 20, 30'.
    """
    m = re.match(r'^(.*\bboxcursor)\.alpharange$', orig_key, flags=re.IGNORECASE)
    if not m:
        return orig_key, False
    return f"{m.group(1)}.pulse", True

def _split_value_comment(s: str):
    """
    Split a 'value[  ;comment]' into ('value', '[  ;comment]'), preserving any
    original spacing before the semicolon. If there is no inline comment, the
    second element is an empty string.
    """
    m = re.match(r'^(.*?)([ \t]*;.*)?$', s)
    return (m.group(1), m.group(2) or '') if m else (s, '')

def _normalize_key_value_if_needed(orig_key: str, value: str) -> str:
    """If key name ends with '.key' (case-insensitive), turn 'a&b&c' into 'a, b, c'."""
    if re.search(r'\.key$', orig_key, flags=re.IGNORECASE):
        parts = [p.strip() for p in value.split('&') if p.strip() != '']
        new_value = ', '.join(parts) if parts else value.strip()
        return new_value
    return value

def process_ini(ini_path, output_stream):
    """
    Core processing: read an INI file, apply all rules, and write the resulting
    lines to `output_stream` (a file-like object such as sys.stdout or
    an io.StringIO instance).
    """
    current_section = ""
    # Track active (non-commented) keys we've seen per section (case-insensitive).
    seen_keys_by_section = {}

    def append_missing_for_section(section_name: str):
        """
        Append any keys configured in append_if_missing[section_name] that were not
        seen as active lines in that section. Appended lines go through handle_line
        so they benefit from the same transformations/normalizations.
        """
        if not section_name:
            return
        section_map = append_if_missing.get(section_name, {})
        if not section_map:
            return
        seen = seen_keys_by_section.get(section_name, set())
        for k, v in section_map.items():
            key_norm = str(k).strip().lower()
            if key_norm not in seen:
                print(f"[{section_name}] Appending missing key: {k}", file=sys.stderr)
                # Route through handle_line for consistency (quotes, transforms, etc.).
                new_lines = handle_line(
                    section=section_name,
                    orig_key=str(k),
                    value=str(v),
                    comment=""
                )
                if new_lines:
                    for ln in new_lines:
                        print(ln, file=output_stream)

    with open(ini_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            raw_line = line.rstrip('\n')

            # 1) Check if it's a [Section] line
            section_match = SECTION_REGEX.match(raw_line)
            if section_match:
                # Before switching sections, finish the previous one by appending missing keys.
                append_missing_for_section(current_section)
                current_section = section_match.group(1).strip().lower()
                print(raw_line, file=output_stream)
                continue

            # 2) Check if it's a key=value line with optional comment
            kv_match = KEY_VALUE_REGEX.match(raw_line)
            if kv_match:
                semicolon = kv_match.group(1)  # ";" or ""
                raw_key = kv_match.group(2)
                raw_value = kv_match.group(3)

                comment_marker = ";" if semicolon == ";" else ""
                clean_key = raw_key.strip()
                # Record only active (non-commented) keys as "present" in this section.
                if comment_marker != ";":
                    seen_keys_by_section.setdefault(current_section, set()).add(clean_key.lower())

                new_lines = handle_line(
                    section=current_section,
                    orig_key=clean_key,
                    value=raw_value,
                    comment=comment_marker
                )

                # Write whatever lines we got back (unless empty => deleted)
                if new_lines:
                    for ln in new_lines:
                        print(ln, file=output_stream)
            else:
                # 3) Not a key-value line => pass it unchanged
                print(raw_line, file=output_stream)

    # End of file: flush appends for the final section.
    append_missing_for_section(current_section)


def main(argv=None):
    """
    CLI entry point.

    Default: patch the INI file in place.
    Optional: --stdout to write patched contents to stdout (like the original script).
    """
    _ensure_utf8_stdio()

    parser = argparse.ArgumentParser(
        description="Update / patch an INI file in-place (default) or write to stdout."
    )
    parser.add_argument(
        "ini_path",
        help="Path to the INI file to process.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write patched INI to stdout instead of modifying the file in place.",
    )

    args = parser.parse_args(argv)

    if args.stdout:
        # write updated content to stdout.
        process_ini(args.ini_path, sys.stdout)
    else:
        # patch in place, creating a .bak backup first.
        backup_path = args.ini_path + ".bak"
        try:
            shutil.copy2(args.ini_path, backup_path)
            print(f"Backup created: {backup_path}", file=sys.stderr)
        except Exception as e:
            print(
                f"WARNING: Failed to create backup '{backup_path}': {e}",
                file=sys.stderr,
            )

        buf = io.StringIO()
        process_ini(args.ini_path, buf)
        new_content = buf.getvalue()
        with open(args.ini_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(new_content)

def handle_line(section, orig_key, value, comment):
    """
    1) Check if key should be deleted (keys_to_delete).
    2) If not deleted, apply value modifications (value_modifications).
    3) Remove enclosing double quotes from the value.
    4) Apply transformations on the key (transformations).
    Return a list of lines to print. If empty => line is removed entirely.
    """
    # Check for key deletion
    for pattern in keys_to_delete.get(section, []):
        if pattern.match(orig_key):
            print(f"[{section}] Deleting line for key: {orig_key}", file=sys.stderr)
            return []

    # Work only on the part before an inline comment; keep the comment to reattach later.
    value_body, inline_comment = _split_value_comment(value)

    # Value modifications
    new_value = value_body
    for (key_rx, val_rx, repl) in value_modifications.get(section, []):
        if key_rx.match(orig_key):
            old_value = new_value
            new_value = val_rx.sub(repl, new_value)
            if new_value != old_value:
                print(
                    f"[{section}] Value modified for key {orig_key}: "
                    f"'{old_value}' => '{new_value}'",
                    file=sys.stderr
                )

    # Automatically remove all double quotes from the value.
    new_value = new_value.replace('"', '')

    # Globally normalize any "*.key" value: a&b&c -> a, b, c
    if re.search(r'\.key$', orig_key, re.IGNORECASE):
        old_v = new_value
        new_value = _normalize_key_value_if_needed(orig_key, new_value)
        if new_value != old_v:
            print(
                f"[global] Normalized .key list for {orig_key}: '{old_v}' => '{new_value}'",
                file=sys.stderr
            )

    # Convert p1/p2 + ".memberX" segments into p1/p3/p5/p7 or p2/p4/p6/p8, and drop the ".memberX" segment from the key path.
    remapped_key, did_remap = _remap_member_key(orig_key)
    if did_remap:
        print(f"[global] Member key remapped: {orig_key} => {remapped_key}", file=sys.stderr)
        orig_key = remapped_key

    # Convert any '<prefix>boxcursor.alpharange' into '<prefix>boxcursor.pulse'
    remapped_key2, did_remap2 = _remap_boxcursor_alpharange(orig_key)
    if did_remap2:
        print(f"[global] Boxcursor alpharange remapped: {orig_key} => {remapped_key2}; value forced to '30, 20, 30'", file=sys.stderr)
        orig_key, new_value = remapped_key2, "30, 20, 30"

    # Expand [Hiscore Info] title.text into six fixed lines
    if section == "hiscore info" and re.match(r"^title\.text$", orig_key, re.IGNORECASE):
        out_lines = [
            f"{comment}title.text.arcade = Ranking Arcade",
            f"{comment}title.text.teamarcade = Ranking Team Arcade",
            f"{comment}title.text.teamcoop = Ranking Team Cooperative",
            f"{comment}title.text.timeattack = Ranking Time Attack",
            f"{comment}title.text.survival = Ranking Survival",
            f"{comment}title.text.survivalcoop = Ranking Survival Cooperative",
        ]
        print(
            f"[{section}] Expanded {orig_key} into 6 title.text.* lines",
            file=sys.stderr
        )
        return out_lines

    # Key transformations
    transformed_lines = apply_key_transformations(section, orig_key, new_value + inline_comment, comment)
    if transformed_lines:
        return transformed_lines

    # Keep as is
    return [f"{comment}{orig_key} = {new_value}{inline_comment}"]

def apply_key_transformations(section, orig_key, value, comment):
    # Special-case [Select Info] where we now want 0-based indices instead of 1-based.
    # This keeps the param rename (row.col -> row-col) but also shifts indices by -1.
    if section == "select info":
        # cell.<row>.<col>.(offset|facing|skip) -> cell.<row-1>-<col-1>.(...)
        m = re.match(
            r"^cell\.([0-9]+)\.([0-9]+)\.(offset|facing|skip)$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            row = int(m.group(1)) - 1
            col = int(m.group(2)) - 1
            suffix = m.group(3).lower()
            new_key = f"cell.{row}-{col}.{suffix}"
            print(
                f"[{section}] Key modified (1-based -> 0-based): {orig_key} => {new_key}",
                file=sys.stderr,
            )
            return [f"{comment}{new_key} = {value}"]

        # p<1|2>.cursor.(active|done).<row>.<col>.(anim|spr|offset|facing|scale) ->
        # p<1|2>.cursor.(active|done).<row-1>-<col-1>.(...)
        m = re.match(
           r"^p([12])\.cursor\.(active|done)\.([0-9]+)\.([0-9]+)\."
            r"(anim|spr|offset|facing|scale)$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            player = m.group(1)
            cursor_state = m.group(2).lower()   # active / done
            row = int(m.group(3)) - 1
            col = int(m.group(4)) - 1
            suffix = m.group(5).lower()
            new_key = f"p{player}.cursor.{cursor_state}.{row}-{col}.{suffix}"
            print(
                f"[{section}] Key modified (1-based -> 0-based): {orig_key} => {new_key}",
                file=sys.stderr,
            )
            return [f"{comment}{new_key} = {value}"]

    section_rules = transformations.get(section, [])
    for (pattern, replacements) in section_rules:
        m = pattern.match(orig_key)
        if m:
            out_lines = []
            for rep in replacements:
                new_key = m.expand(rep)
                val_out = value
                out_lines.append(f"{comment}{new_key} = {val_out}")
                print(f"[{section}] Key modified: {orig_key} => {new_key}", file=sys.stderr)
            # Stop after the first matching rule to avoid duplicate transformations.
            return out_lines
    return None


if __name__ == "__main__":
    main()
