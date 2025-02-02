#!/usr/bin/env python
#
# Copyright (c) 2008-2012 by Jaroslav Kysela <perex@perex.cz>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from hda_codec import HDACodec, HDA_card_list, EAPDBTL_BITS, PIN_WIDGET_CONTROL_BITS, PIN_WIDGET_CONTROL_VREF, \
    DIG1_BITS, GPIO_IDS, HDA_INPUT, HDA_OUTPUT

DIFF_FILE = "/tmp/hda-analyze.diff"

CODEC_TREE = {}
DIFF_TREE = {}


def get_fixed_font():
    return Pango.FontDescription("Misc Fixed,Courier Bold 9")


class HDASignal(GObject.GObject):

    def __init__(self):
        super(HDASignal, self).__init__()


GObject.signal_new("hda-codec-changed", HDASignal, GObject.SignalFlags.RUN_FIRST, None,
                   (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT))
GObject.signal_new("hda-node-changed", HDASignal, GObject.SignalFlags.RUN_FIRST, None,
                   (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT))

HDA_SIGNAL = HDASignal()


def do_diff1(codec, diff1):
    from difflib import unified_diff
    diff = unified_diff(diff1.split('\n'), codec.dump().split('\n'), n=8, lineterm='')
    diff = '\n'.join(list(diff))
    if len(diff) > 0:
        diff = 'Diff for codec %i/%i (%s):\n' % (codec.card, codec.device, codec.name) + diff
    return diff


def do_diff():
    diff = ''
    hw = 0
    for card in CODEC_TREE:
        for codec in CODEC_TREE[card]:
            c = CODEC_TREE[card][codec]
            if c.hwaccess:
                hw += 1
            diff += do_diff1(c, DIFF_TREE[card][codec])
    if len(diff) > 0:
        open(DIFF_FILE, "w+").write(diff + '\n')
        print("Diff was stored to: %s" % DIFF_FILE)
    return (diff and hw > 0) and True or False


class NodeGui(Gtk.ScrolledWindow):

    def __init__(self, card=None, codec=None, node=None, doframe=False):
        super(NodeGui, self).__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.read_all = self.__read_all_none
        self.node = None
        self.codec = None
        self.popups = []
        if card and not codec and not node:
            self.__build_card(card, doframe)
        elif codec and not card and not node:
            self.__build_codec(codec, doframe)
        elif node and not card and not codec:
            self.__build_node(node, doframe)
        self.connect("destroy", self.__destroy)
        self.codec_changed = HDA_SIGNAL.connect("hda-codec-changed", self.hda_codec_changed)
        self.node_changed = HDA_SIGNAL.connect("hda-node-changed", self.hda_node_changed)
        self.read_all()
        self.show_all()

    def __destroy(self, widget):
        HDA_SIGNAL.handler_disconnect(self.codec_changed)
        HDA_SIGNAL.handler_disconnect(self.node_changed)

    def __read_all_none(self):
        pass

    def hda_codec_changed(self, obj, widget, codec):
        if widget != self:
            if self.read_all and self.codec == codec:
                self.read_all()

    def hda_node_changed(self, obj, widget, node):
        if widget != self:
            if self.read_all and self.node == node:
                self.read_all()

    def show_popup(self, text):
        screen_width = Gdk.Screen.width()
        screen_height = Gdk.Screen.height()

        popup_win = Gtk.Window(Gtk.WindowType.POPUP)
        popup_win.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(0xffff, 0xd700, 0))
        frame = Gtk.Frame()
        popup_win.add(frame)
        label = Gtk.Label()
        label.modify_font(get_fixed_font())
        if text[-1] == '\n':
            text = text[:-1]
        label.set_text(text)
        frame.add(label)
        popup_win.move(screen_width + 10, screen_height + 10)
        popup_win.show_all()
        popup_width, popup_height = popup_win.get_size()

        rootwin = self.get_screen().get_root_window()
        _, x, y, _ = rootwin.get_pointer()

        pos_x = x - popup_width / 2
        if pos_x < 0:
            pos_x = 0
        if pos_x + popup_width > screen_width:
            pos_x = screen_width - popup_width
        pos_y = y + 16
        if pos_y < 0:
            pox_y = 0
        if pos_y + popup_height > screen_height:
            pos_y = screen_height - popup_height

        popup_win.move(int(pos_x), int(pos_y))
        return popup_win

    def __popup_motion_notify(self, widget, event=None):
        for popup in self.popups:
            if popup[1] == widget and not popup[0]:
                popup[0] = self.show_popup(popup[2](*popup[3]))

    def __popup_leave_notify(self, widget, event=None):
        for popup in self.popups:
            if popup[1] == widget and popup[0]:
                popup[0].destroy()
                popup[0] = None

    def make_popup(self, widget, gettext, data):
        widget.connect("motion-notify-event", self.__popup_motion_notify)
        widget.connect("leave-notify-event", self.__popup_leave_notify)
        self.popups.append([None, widget, gettext, data])

    def __create_text(self, callback):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.IN)

        text_view = Gtk.TextView()
        fontName = get_fixed_font()
        text_view.modify_font(fontName)
        scrolled_window.add(text_view)

        buffer = Gtk.TextBuffer(None)
        text_view.set_buffer(buffer)
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.connect("visibility-notify-event", callback)

        text_view.set_wrap_mode(True)

        return scrolled_window, buffer

    def __new_text_view(self, text=None):
        text_view = Gtk.TextView()
        text_view.set_border_width(4)
        fontName = get_fixed_font()
        text_view.modify_font(fontName)
        if not text is None:
            buffer = Gtk.TextBuffer()
            iter = buffer.get_iter_at_offset(0)
            if text[-1] == '\n':
                text = text[:-1]
            buffer.insert(iter, text)
            text_view.set_buffer(buffer)
            text_view.set_editable(False)
            text_view.set_cursor_visible(False)
        return text_view

    def __build_node_caps(self, node):
        frame = Gtk.Frame.new('Node Caps')
        frame.set_border_width(4)
        if len(node.wcaps_list) == 0:
            return frame
        str = ''
        for i in node.wcaps_list:
            str += node.wcap_name(i) + '\n'
        frame.add(self.__new_text_view(text=str))
        return frame

    def __node_connection_toggled(self, widget, row, data):
        model, node = data
        if not model[row][0]:
            if node.set_active_connection(int(row)):
                HDA_SIGNAL.emit("hda-node-changed", self, node)
        for r in model:
            r[0] = False
        idx = 0
        for r in model:
            r[0] = node.active_connection == idx
            idx += 1

    def __build_connection_list(self, node):
        frame = Gtk.Frame.new('Connection List')
        frame.set_border_width(4)
        sw = Gtk.ScrolledWindow()
        # sw.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        frame.add(sw)
        if node.conn_list and node.connections:
            model = Gtk.ListStore(GObject.TYPE_BOOLEAN, GObject.TYPE_STRING)
            idx = 0
            for i in node.connections:
                iter = model.append()
                node1 = node.codec.get_node(node.connections[idx])
                model.set(iter, 0, node.active_connection == idx, 1, node1.name())
                idx += 1
            self.connection_model = model
            treeview = Gtk.TreeView(model)
            treeview.set_rules_hint(True)
            treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
            treeview.set_size_request(300, 30 + len(node.connections) * 25)
            renderer = Gtk.CellRendererToggle()
            renderer.set_radio(True)
            if not node.active_connection is None:
                renderer.connect("toggled", self.__node_connection_toggled, (model, node))
            column = Gtk.TreeViewColumn("Active", renderer, active=0)
            treeview.append_column(column)
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn("Source Node", renderer, text=1)
            treeview.append_column(column)
            sw.add(treeview)
        return frame

    def __amp_mute_toggled(self, button, data):
        caps, vals, idx = data
        val = button.get_active()
        if vals.set_mute(idx, val):
            HDA_SIGNAL.emit("hda-node-changed", self, vals.node)
        button.set_active(vals.vals[idx] & 0x80)

    def __amp_value_changed(self, adj, data):
        caps, vals, idx = data
        val = int(adj.get_value())
        if vals.set_value(idx, val):
            HDA_SIGNAL.emit("hda-node-changed", self, vals.node)
        adj.set_value(vals.vals[idx] & 0x7f)

    def __ctl_mute_toggled(self, adj, data):
        ctl, idx = data

    def __ctl_value_changed(self, adj, data):
        ctl, idx = data

    def __popup_show_ctl(self, ctl, idx):
        return ctl.get_text_info(idx - ctl.hdactl.amp_idx)

    def __build_amps(self, node):

        def build_caps(title, caps, vals):
            if caps and caps.cloned:
                title += ' (Global)'
            frame = Gtk.Frame.new(title)
            frame.set_border_width(4)
            vbox = Gtk.VBox(False, 0)
            if caps:
                if caps.ofs != None:
                    str = 'Offset:          %d\n' % caps.ofs
                    str += 'Number of steps: %d\n' % caps.nsteps
                    str += 'Step size:       %d\n' % caps.stepsize
                str += 'Mute:            %s\n' % (caps.mute and "True" or "False")
                vbox.pack_start(self.__new_text_view(text=str), True, True, 0)
                idx = 0
                frame1 = None
                vbox1 = None
                self.amp_checkbuttons[caps.dir] = []
                self.amp_adjs[caps.dir] = []
                self.mixer_elems[caps.dir] = []
                ctls = node.get_mixercontrols()
                for val in vals.vals:
                    if vals.stereo and idx & 1 == 0:
                        frame1 = Gtk.Frame()
                        vbox.pack_start(frame1, False, False, 0)
                        vbox1 = Gtk.VBox(False, 0)
                        frame1.add(vbox1)
                    hbox = Gtk.HBox(False, 0)
                    label = Gtk.Label(label='Val[%d]' % idx)
                    hbox.pack_start(label, False, False, 0)
                    if caps.mute:
                        checkbutton = Gtk.CheckButton('Mute')
                        checkbutton.connect("toggled", self.__amp_mute_toggled, (caps, vals, idx))
                        # checkbutton.set_active(True)
                        self.amp_checkbuttons[caps.dir].append(checkbutton)
                        hbox.pack_start(checkbutton, False, False, 0)
                    else:
                        self.amp_checkbuttons[caps.dir].append(None)
                    if caps.stepsize > 0:
                        adj = Gtk.Adjustment((val & 0x7f) % (caps.nsteps + 1), 0.0, caps.nsteps + 1, 1.0, 1.0, 1.0)
                        scale = Gtk.HScale.new(adj)
                        scale.set_digits(0)
                        scale.set_value_pos(Gtk.PositionType.RIGHT)
                        adj.connect("value_changed", self.__amp_value_changed, (caps, vals, idx))
                        self.amp_adjs[caps.dir].append(adj)
                        hbox.pack_start(scale, True, True, 0)
                    else:
                        self.amp_adjs[caps.dir].append(None)
                    sep = False
                    for ctl in ctls:
                        if ctl.hdactl.amp_index_match(idx):
                            if ctl.stype == 'boolean':
                                if not sep:
                                    hbox.pack_start(Gtk.VSeparator(), False, False, 0)
                                    hbox.pack_start(Gtk.Label('CTLIFC'), False, False, 0)
                                    sep = True
                                checkbutton = Gtk.CheckButton('Mute')
                                checkbutton.connect("toggled", self.__ctl_mute_toggled, (ctl, idx))
                                self.make_popup(checkbutton, self.__popup_show_ctl, (ctl, idx))
                                hbox.pack_start(checkbutton, False, False, 0)
                    for ctl in ctls:
                        if ctl.hdactl.amp_index_match(idx):
                            if ctl.stype.startswith('integer'):
                                if not sep:
                                    hbox.pack_start(Gtk.VSeparator(), False, False, 0)
                                    sep = True
                                adj = Gtk.Adjustment(0, ctl.min, ctl.max, ctl.step, ctl.step, ctl.step)
                                scale = Gtk.HScale.new(adj)
                                scale.set_digits(0)
                                scale.set_value_pos(Gtk.PositionType.RIGHT)
                                adj.connect("value_changed", self.__ctl_value_changed, (ctl, idx))
                                self.make_popup(scale, self.__popup_show_ctl, (ctl, idx))
                                hbox.pack_start(scale, True, True, 0)
                    if vbox1:
                        vbox1.pack_start(hbox, False, False, 0)
                    else:
                        vbox.pack_start(hbox, False, False, 0)
                    idx += 1
            frame.add(vbox)
            return frame

        self.amp_checkbuttons = {}
        self.amp_adjs = {}
        self.mixer_elems = {}
        hbox = Gtk.HBox(False, 0)
        c = build_caps('Input Amplifier', node.in_amp and node.amp_caps_in or None,
                       node.in_amp and node.amp_vals_in or None)
        hbox.pack_start(c, True, True, 0)
        c = build_caps('Output Amplifier', node.out_amp and node.amp_caps_out or None,
                       node.out_amp and node.amp_vals_out or None)
        hbox.pack_start(c, True, True, 0)

        return hbox

    def __pincap_eapdbtl_toggled(self, button, data):
        node, name = data
        if node.eapdbtl_set_value(name, button.get_active()):
            HDA_SIGNAL.emit("hda-node-changed", self, node)
        button.set_active(name in node.pincap_eapdbtl)

    def __pinctls_toggled(self, button, data):
        node, name = data
        if node.pin_widget_control_set_value(name, button.get_active()):
            HDA_SIGNAL.emit("hda-node-changed", self, node)
        button.set_active(name in node.pinctl)

    def __pinctls_vref_change(self, combobox, node):
        index = combobox.get_active()
        idx1 = 0
        for name in PIN_WIDGET_CONTROL_VREF:
            if not name: continue
            if idx1 == index:
                if node.pin_widget_control_set_value('vref', name):
                    HDA_SIGNAL.emit("hda-node-changed", self, node)
                break
            idx1 += 1
        idx = idx1 = 0
        for name in PIN_WIDGET_CONTROL_VREF:
            if name == node.pinctl_vref:
                combobox.set_active(idx1)
                break
            if name != None:
                idx1 += 1

    def __build_pin(self, node):
        hbox = Gtk.HBox(False, 0)

        if node.pincap or node.pincap_vref or node.pincap_eapdbtl:
            vbox = Gtk.VBox(False, 0)
            if node.pincap or node.pincap_vref:
                frame = Gtk.Frame.new('PIN Caps')
                frame.set_border_width(4)
                str = ''
                for i in node.pincap:
                    str += node.pincap_name(i) + '\n'
                for i in node.pincap_vref:
                    str += 'VREF_%s\n' % i
                frame.add(self.__new_text_view(text=str))
                vbox.pack_start(frame, True, True, 0)
            if 'EAPD' in node.pincap:
                frame = Gtk.Frame.new('EAPD')
                frame.set_border_width(4)
                vbox1 = Gtk.VBox(False, 0)
                self.pincap_eapdbtls_checkbuttons = []
                for name in EAPDBTL_BITS:
                    checkbutton = Gtk.CheckButton(name)
                    checkbutton.connect("toggled", self.__pincap_eapdbtl_toggled, (node, name))
                    self.pincap_eapdbtls_checkbuttons.append(checkbutton)
                    vbox1.pack_start(checkbutton, False, False, 0)
                frame.add(vbox1)
                vbox.pack_start(frame, False, False, 0)
            hbox.pack_start(vbox, True, True, 0)

        vbox = Gtk.VBox(False, 0)

        frame = Gtk.Frame.new('Config Default')
        frame.set_border_width(4)
        str = 'Jack connection: %s\n' % node.jack_conn_name
        str += 'Jack type:       %s\n' % node.jack_type_name
        str += 'Jack location:   %s\n' % node.jack_location_name
        str += 'Jack location2:  %s\n' % node.jack_location2_name
        str += 'Jack connector:  %s\n' % node.jack_connector_name
        str += 'Jack color:      %s\n' % node.jack_color_name
        if 'NO_PRESENCE' in node.defcfg_misc:
            str += 'No presence\n'
        frame.add(self.__new_text_view(text=str))
        vbox.pack_start(frame, True, True, 0)

        frame = Gtk.Frame.new('Widget Control')
        frame.set_border_width(4)
        vbox1 = Gtk.VBox(False, 0)
        self.pin_checkbuttons = []
        for name in PIN_WIDGET_CONTROL_BITS:
            checkbutton = Gtk.CheckButton(name)
            checkbutton.connect("toggled", self.__pinctls_toggled, (node, name))
            self.pin_checkbuttons.append(checkbutton)
            vbox1.pack_start(checkbutton, False, False, 0)
        if node.pincap_vref:
            combobox = Gtk.ComboBoxText()
            for name in PIN_WIDGET_CONTROL_VREF:
                if name:
                    combobox.append_text(name)
            combobox.connect("changed", self.__pinctls_vref_change, node)
            self.pincap_vref_combobox = combobox
            hbox1 = Gtk.HBox(False, 0)
            label = Gtk.Label(label='VREF')
            hbox1.pack_start(label, False, False, 0)
            hbox1.pack_start(combobox, True, True, 0)
            vbox1.pack_start(hbox1, False, False, 0)
        frame.add(vbox1)
        vbox.pack_start(frame, False, False, 0)

        hbox.pack_start(vbox, True, True, 0)
        return hbox

    def __build_mix(self, node):
        hbox = Gtk.HBox(False, 0)
        return hbox

    def __sdi_select_changed(self, adj, node):
        val = int(adj.get_value())
        if node.sdi_select_set_value(val):
            HDA_SIGNAL.emit("hda-node-changed", self, node)
        adj.set_value(node.sdi_select)

    def __dig1_toggled(self, button, data):
        node, name = data
        val = button.get_active()
        if node.dig1_set_value(name, val):
            HDA_SIGNAL.emit("hda-node-changed", self, node)
        button.set_active(name in node.dig1)

    def __dig1_category_activate(self, entry, node):
        val = entry.get_text()
        if val.lower().startswith('0x'):
            val = int(val[2:], 16)
        else:
            try:
                val = int(val)
            except:
                print("Unknown category value '%s'" % val)
                return
        if node.dig1_set_value('category', val):
            HDA_SIGNAL.emit("hda-node-changed", self, node)
        entry.set_text("0x%02x" % node.dig1_category)

    def __build_aud(self, node):
        vbox = Gtk.VBox(False, 0)

        frame = Gtk.Frame.new('Converter')
        frame.set_border_width(4)
        str = 'Audio Stream:\t%s\n' % node.aud_stream
        str += 'Audio Channel:\t%s\n' % node.aud_channel
        if node.format_ovrd:
            str += 'Rates:\t\t%s\n' % node.pcm_rates[:6]
            if len(node.pcm_rates) > 6:
                str += '\t\t\t\t%s\n' % node.pcm_rates[6:]
            str += 'Bits:\t\t%s\n' % node.pcm_bits
            str += 'Streams:\t%s\n' % node.pcm_streams
        else:
            str += 'Global Rates:\t%s\n' % node.codec.pcm_rates[:6]
            if len(node.codec.pcm_rates) > 6:
                str += '\t\t%s\n' % node.codec.pcm_rates[6:]
            str += 'Global Bits:\t%s\n' % node.codec.pcm_bits
            str += 'Global Streams:\t%s\n' % node.codec.pcm_streams
        frame.add(self.__new_text_view(text=str))
        vbox.pack_start(frame, True, True, 0)

        if not node.sdi_select is None:
            hbox1 = Gtk.HBox(False, 0)
            frame = Gtk.Frame.new()
            adj = Gtk.Adjustment(node.sdi_select, 0.0, 16.0, 1.0, 1.0, 1.0)
            self.sdi_select_adj = adj
            scale = Gtk.HScale.new(adj)
            scale.set_digits(0)
            scale.set_value_pos(Gtk.PositionType.LEFT)
            scale.set_size_request(200, 16)
            adj.connect("value_changed", self.__sdi_select_changed, node)
            frame.add(scale)
            hbox1.pack_start(frame, False, False, 0)
            vbox.pack_start(hbox1, False, False, 0)

        if node.digital:
            hbox1 = Gtk.HBox(False, 0)
            frame = Gtk.Frame.new('Digital Converter')
            vbox1 = Gtk.VBox(False, 0)
            self.digital_checkbuttons = []
            for name in DIG1_BITS:
                checkbutton = Gtk.CheckButton(name)
                checkbutton.connect("toggled", self.__dig1_toggled, (node, name))
                self.digital_checkbuttons.append(checkbutton)
                vbox1.pack_start(checkbutton, False, False, 0)
            frame.add(vbox1)
            hbox1.pack_start(frame, True, True, 0)
            frame = Gtk.Frame.new('Digital Converter Category')
            entry = Gtk.Entry()
            self.dig_category_entry = entry
            entry.set_width_chars(4)
            entry.connect("activate", self.__dig1_category_activate, node)
            frame.add(entry)
            hbox1.pack_start(frame, True, True, 0)
            vbox.pack_start(hbox1, False, False, 0)

        return vbox

    def __build_device(self, device):
        vbox = Gtk.VBox(False, 0)
        frame = Gtk.Frame.new('Device')
        frame.set_border_width(4)
        hbox = Gtk.HBox(False, 0)
        s = 'name=' + str(device.name) + ', type=' + str(device.type) + ', device=' + str(device.device)
        label = Gtk.Label(label=s)
        hbox.pack_start(label, False, False, 0)
        frame.add(hbox)
        vbox.pack_start(frame, True, True, 0)
        return vbox

    def __build_controls(self, ctrls):
        vbox = Gtk.VBox(False, 0)
        frame = Gtk.Frame.new('Controls')
        frame.set_border_width(4)
        vbox1 = Gtk.VBox(False, 0)
        for ctrl in ctrls:
            hbox1 = Gtk.HBox(False, 0)
            vbox1.pack_start(hbox1, False, False, 0)
            s = (ctrl.iface and ('iface=' + ctrl.iface + ',') or '') + 'name=' + str(ctrl.name) + ', index=' + str(
                ctrl.index) + ', device=' + str(ctrl.device)
            label = Gtk.Label(label=s)
            hbox1.pack_start(label, False, False, 0)
            if ctrl.amp_chs:
                hbox1 = Gtk.HBox(False, 0)
                vbox1.pack_start(hbox1, False, False, 0)
                s = '  chs=' + str(ctrl.amp_chs) + ', dir=' + str(ctrl.amp_dir) + ', idx=' + str(
                    ctrl.amp_idx) + ', ofs=' + str(ctrl.amp_ofs)
                label = Gtk.Label(label=s)
                hbox1.pack_start(label, False, False, 0)
        frame.add(vbox1)
        vbox.pack_start(frame, True, True, 0)
        return vbox

    def __build_proc(self, node):
        frame = Gtk.Frame.new('Processing Caps')
        frame.set_border_width(4)
        str = 'benign=%i\nnumcoef=%i\n' % (node.proc_benign, node.proc_numcoef)
        frame.add(self.__new_text_view(text=str))
        return frame

    def __read_all_node(self):
        node = self.node
        if node.wtype_id in ['AUD_IN', 'AUD_OUT']:
            if not node.sdi_select is None:
                self.sdi_select_adj.set_value(node.sdi_select)
            if node.digital:
                idx = 0
                for name in DIG1_BITS:
                    checkbutton = self.digital_checkbuttons[idx]
                    checkbutton.set_active(node.digi1 & (1 << DIG1_BITS[name]))
                    idx += 1
                self.dig_category_entry.set_text("0x%x" % node.dig1_category)
        elif node.wtype_id == 'PIN':
            if 'EAPD' in node.pincap:
                idx = 0
                for name in EAPDBTL_BITS:
                    checkbutton = self.pincap_eapdbtls_checkbuttons[idx]
                    checkbutton.set_active(node.pincap_eapdbtls & (1 << EAPDBTL_BITS[name]))
                    idx += 1
            idx = 0
            for name in PIN_WIDGET_CONTROL_BITS:
                checkbutton = self.pin_checkbuttons[idx]
                checkbutton.set_active(node.pinctls & (1 << PIN_WIDGET_CONTROL_BITS[name]))
                idx += 1
            idx = active = 0
            for name in PIN_WIDGET_CONTROL_VREF:
                if name == node.pinctl_vref: active = idx
                if name: idx += 1
            if node.pincap_vref:
                self.pincap_vref_combobox.set_active(active)
        a = []
        if node.in_amp:
            a.append((HDA_INPUT, node.amp_caps_in, node.amp_vals_in))
        if node.out_amp:
            a.append((HDA_OUTPUT, node.amp_caps_out, node.amp_vals_out))
        for dir, caps, vals in a:
            for idx in range(len(vals.vals)):
                val = vals.vals[idx]
                checkbutton = self.amp_checkbuttons[dir][idx]
                if checkbutton:
                    checkbutton.set_active(val & 0x80 and True or False)
                adj = self.amp_adjs[dir][idx]
                if adj:
                    adj.set_value((val & 0x7f) % (caps.nsteps + 1))
                idx += 1
        if hasattr(self, 'connection_model'):
            for r in self.connection_model:
                r[0] = False
            idx = 0
            for r in self.connection_model:
                r[0] = node.active_connection == idx
                idx += 1

    def __build_node(self, node, doframe=False):
        self.node = node
        self.mytitle = node.name()
        if doframe:
            mframe = Gtk.Frame.new(self.mytitle)
            mframe.set_border_width(4)
        else:
            mframe = Gtk.Table()

        vbox = Gtk.VBox(False, 0)
        dev = node.get_device()
        if not dev is None:
            vbox.pack_start(self.__build_device(dev), False, False, 0)
        ctrls = node.get_controls()
        if ctrls:
            node.get_mixercontrols()  # workaround
            vbox.pack_start(self.__build_controls(ctrls), False, False, 0)
        hbox = Gtk.HBox(False, 0)
        hbox.pack_start(self.__build_node_caps(node), True, True, 0)
        hbox.pack_start(self.__build_connection_list(node), True, True, 0)
        vbox.pack_start(hbox, False, False, 0)
        if node.in_amp or node.out_amp:
            vbox.pack_start(self.__build_amps(node), False, False, 0)
        if node.wtype_id == 'PIN':
            vbox.pack_start(self.__build_pin(node), False, False, 0)
        elif node.wtype_id in ['AUD_IN', 'AUD_OUT']:
            vbox.pack_start(self.__build_aud(node), False, False, 0)
        else:
            if not node.wtype_id in ['AUD_MIX', 'BEEP', 'AUD_SEL']:
                print('Node type %s has no GUI support' % node.wtype_id)
        if node.proc_wid:
            vbox.pack_start(self.__build_proc(node), False, False, 0)

        mframe.add(vbox)
        self.add_with_viewport(mframe)

        self.read_all = self.__read_all_node

    def __build_codec_info(self, codec):
        vbox = Gtk.VBox(False, 0)

        frame = Gtk.Frame.new('Codec Identification')
        frame.set_border_width(4)
        str = 'Audio Fcn Group: %s\n' % (codec.afg and "0x%02x" % codec.afg or "N/A")
        if codec.afg:
            str += 'AFG Function Id: 0x%02x (unsol %u)\n' % (codec.afg_function_id, codec.afg_unsol)
        str += 'Modem Fcn Group: %s\n' % (codec.mfg and "0x%02x" % codec.mfg or "N/A")
        if codec.mfg:
            str += 'MFG Function Id: 0x%02x (unsol %u)\n' % (codec.mfg_function_id, codec.mfg_unsol)
        str += 'Vendor ID:\t 0x%08x\n' % codec.vendor_id
        str += 'Subsystem ID:\t 0x%08x\n' % codec.subsystem_id
        str += 'Revision ID:\t 0x%08x\n' % codec.revision_id
        frame.add(self.__new_text_view(text=str))
        vbox.pack_start(frame, False, False, 0)

        frame = Gtk.Frame.new('PCM Global Capabilities')
        frame.set_border_width(4)
        str = 'Rates:\t\t %s\n' % codec.pcm_rates[:6]
        if len(codec.pcm_rates) > 6:
            str += '\t\t %s\n' % codec.pcm_rates[6:]
        str += 'Bits:\t\t %s\n' % codec.pcm_bits
        str += 'Streams:\t %s\n' % codec.pcm_streams
        frame.add(self.__new_text_view(text=str))
        vbox.pack_start(frame, False, False, 0)

        return vbox

    def __build_codec_amps(self, codec):

        def build_caps(title, caps):
            frame = Gtk.Frame.new(title)
            frame.set_border_width(4)
            if caps and caps.ofs != None:
                str = 'Offset:\t\t %d\n' % caps.ofs
                str += 'Number of steps: %d\n' % caps.nsteps
                str += 'Step size:\t %d\n' % caps.stepsize
                str += 'Mute:\t\t %s\n' % (caps.mute and "True" or "False")
                frame.add(self.__new_text_view(text=str))
            return frame

        hbox = Gtk.HBox(False, 0)
        c = build_caps('Global Input Amplifier Caps', codec.amp_caps_in)
        hbox.pack_start(c, True, True, 0)
        c = build_caps('Global Output Amplifier Caps', codec.amp_caps_out)
        hbox.pack_start(c, True, True, 0)

        return hbox

    def __gpio_toggled(self, button, xxx_todo_changeme):
        (codec, id, idx) = xxx_todo_changeme
        if codec.gpio.set(id, idx, button.get_active()):
            HDA_SIGNAL.emit("hda-codec-changed", self, codec)
        button.set_active(codec.gpio.test(id, idx))

    def __build_codec_gpio(self, codec):
        frame = Gtk.Frame.new('GPIO')
        frame.set_border_width(4)
        hbox = Gtk.HBox(False, 0)
        str = 'IO Count:    %d\n' % codec.gpio_max
        str += 'O Count:     %d\n' % codec.gpio_o
        str += 'I Count:     %d\n' % codec.gpio_i
        str += 'Unsolicited: %s\n' % (codec.gpio_unsol and "True" or "False")
        str += 'Wake:        %s\n' % (codec.gpio_wake and "True" or "False")
        hbox.pack_start(self.__new_text_view(text=str), False, False, 0)
        frame.add(hbox)
        self.gpio_checkbuttons = []
        for id in GPIO_IDS:
            id1 = id == 'direction' and 'out-dir' or id
            frame1 = Gtk.Frame.new(id1)
            frame1.set_border_width(4)
            vbox1 = Gtk.VBox(False, 0)
            self.gpio_checkbuttons.append([])
            for i in range(codec.gpio_max):
                checkbutton = checkbutton = Gtk.CheckButton('[%d]' % i)
                checkbutton.connect("toggled", self.__gpio_toggled, (codec, id, i))
                self.gpio_checkbuttons[-1].append(checkbutton)
                vbox1.pack_start(checkbutton, False, False, 0)
            frame1.add(vbox1)
            hbox.pack_start(frame1, False, False, 0)
        return frame

    def __read_all_codec(self):
        idx = 0
        for id in GPIO_IDS:
            for i in range(self.codec.gpio_max):
                self.gpio_checkbuttons[idx][i].set_active(self.codec.gpio.test(id, i))
            idx += 1

    def __build_codec(self, codec, doframe=False):
        self.codec = codec
        self.mytitle = codec.name
        if doframe:
            mframe = Gtk.Frame.new(self.mytitle)
            mframe.set_border_width(4)
        else:
            mframe = Gtk.Table()

        vbox = Gtk.VBox(False, 0)
        vbox.pack_start(self.__build_codec_info(codec), False, False, 0)
        vbox.pack_start(self.__build_codec_amps(codec), False, False, 0)
        vbox.pack_start(self.__build_codec_gpio(codec), False, False, 0)
        mframe.add(vbox)
        self.add_with_viewport(mframe)
        self.read_all = self.__read_all_codec

    def __build_card_info(self, card):
        str = 'Card:       %s\n' % card.card
        str += 'Id:         %s\n' % card.id
        str += 'Driver:     %s\n' % card.driver
        str += 'Name:       %s\n' % card.name
        str += 'LongName:   %s\n' % card.longname
        return self.__new_text_view(text=str)

    def __build_card(self, card, doframe=False):
        self.mytitle = card.name
        if doframe:
            mframe = Gtk.Frame.new(self.mytitle)
            mframe.set_border_width(4)
        else:
            mframe = Gtk.Table()

        vbox = Gtk.VBox(False, 0)
        vbox.pack_start(self.__build_card_info(card), False, False, 0)
        mframe.add(vbox)
        self.add_with_viewport(mframe)


class SimpleProgressDialog(Gtk.Dialog):

    def __init__(self, title):
        super(SimpleProgressDialog, self).__init__()
        self.set_title(title)
        self.set_modal(True)
        self.set_deletable(False)

        box = self.get_child()

        box.pack_start(Gtk.Label(), False, False, 0)
        self.progressbar = Gtk.ProgressBar()
        box.pack_start(self.progressbar, False, False, 0)

    def set_fraction(self, fraction):
        self.progressbar.set_fraction(fraction)
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


class TrackWindows:

    def __init__(self):
        self.windows = []

    def add(self, win):
        if not win in self.windows:
            self.windows.append(win)

    def close(self, win):
        if win in self.windows:
            self.windows.remove(win)
            if not self.windows:
                self.do_diff(win)
                Gtk.main_quit()

    def do_diff(self, widget):
        if do_diff():
            dialog = Gtk.MessageDialog(widget, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                       Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO,
                                       "HDA-Analyzer: Would you like to revert\n"
                                       "settings for all HDA codecs?")
            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.YES:
                for card in CODEC_TREE:
                    for codec in CODEC_TREE[card]:
                        CODEC_TREE[card][codec].revert()
                print("Settings for all codecs were reverted...")


TRACKER = TrackWindows()
