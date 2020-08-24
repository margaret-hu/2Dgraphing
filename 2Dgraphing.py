#!/usr/bin/env python3
import sys, re, gi, cairo, math
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GLib, Pango

class GuiControl:
    def __init__(self, l, d, x0, x1, y0, y1, debug=False):
        size = 500 # Beginning size
        self.debug = debug
        self.png_size = 500
        self.layer = l
        layer_count = len(l)
        self.visible_layer = [True for i in range(layer_count)]
        self.x_min = x0
        self.x_max = x1
        self.y_min = y0
        self.y_max = y1
        dx = self.x_max - self.x_min
        dy = self.y_max - self.y_min
        self.x_data_range = dx
        self.y_data_range = dy
        self.max_data_range = dx if dx > dy else dy
        self.data = self.rescale(d)
        self.zoom_size = size
        self.zoom_step = 100
        self.zoom_min = 200
        self.zoom_max = 2000
        self.resolution = 2000
        self.line_width = 4
        self.darea = None
        self.loc_label = None
        self.loc_entry = None
        self.layer_surface = ()
        self.view_window_wh = [size, size] # width height
        self.world_window_anchor = [0, size]
        self.radar = None
        self.radar_size = 200
        
    def rescale(self, d):
        new_data = []
        for l in d:
            new_list = []
            #print("list has", l)
            for shape in l:
                two_parts = []
                component = shape.split('~~~')
                two_parts.append(component[0]) # Shape type
                line_segment = False
                if component[0] == 'l':
                    line_segment = True
                number_tuple = self.normalize(component[1:], line_segment)
                two_parts.append(number_tuple)
                new_list.append(two_parts)
            new_data.append(new_list)
        return new_data
        
    def normalize(self, nums, is_line):
        f_nums = [float(n) for n in nums]
        if len(f_nums) == 2:
            f_nums[0] = (f_nums[0] - self.x_min) / self.max_data_range
            f_nums[1] = (f_nums[1] - self.y_min) / self.max_data_range
            return (f_nums[0], f_nums[1])
        if len(f_nums) == 4:
            if is_line:
                x0 = (f_nums[0] - self.x_min) / self.max_data_range
                y0 = (f_nums[1] - self.y_min) / self.max_data_range
                x1 = (f_nums[2] - self.x_min) / self.max_data_range
                y1 = (f_nums[3] - self.y_min) / self.max_data_range
                return (x0, y0, x1, y1)
            if f_nums[0] > f_nums[2]:
                x_small = f_nums[2]
                x_big = f_nums[0]
            else:
                x_small = f_nums[0]
                x_big = f_nums[2]
            x_small = (x_small - self.x_min) / self.max_data_range
            x_big = (x_big - self.x_min) / self.max_data_range
            if f_nums[1] > f_nums[3]:
                y_small = f_nums[3]
                y_big = f_nums[1]
            else:
                y_small = f_nums[1]
                y_big = f_nums[3]
            y_small = (y_small - self.y_min) / self.max_data_range
            y_big = (y_big - self.y_min) / self.max_data_range
            return (x_small, y_small, x_big, y_big)

def find_min_max(mylist, fn):
    if mylist:
        if fn < mylist[0]:
            mylist[0] = fn
        if fn > mylist[1]:
            mylist[1] = fn
    else:
        mylist.append(fn) # Minimum value
        mylist.append(fn) # Maximum value

def parse_input(files):
    x_min_max = []
    y_min_max = []
    layers = []
    data = []
    for file_name in files:
        layer_name = file_name + "~~~anonymous~~~s~~~:~~~"
        layers.append(layer_name)
        data.append([])
        slot = -1
        with open(file_name) as f:
            for num, line in enumerate(f, 1):
                line = line.strip()
                if line == '' or line[0] == '#':
                    continue
                if line[0] == '"':
                    pattern = r'^"(.+)\s([bgrcmywopslte])' # Layer name and color
                    pattern += r'(-|--|-\.|:)' # Line style
                    pattern += r'([xf]?)$' # Fill pattern
                    #pattern = r'^".+\s[bgrcmywopslt](-|--|-\.|:)[xf]?$'
                    m = re.search(pattern, line)
                    if not m:
                        print("\twrong syntax in layer spec")
                        print(file_name,":", num, line)
                        raise Exception("layer parsing error")
                    layer_name = file_name
                    for n in [m.group(1), m.group(2), m.group(3), m.group(4)]:
                        layer_name += "~~~" + n.strip()
                    if layer_name in layers:
                        slot = layers.index(layer_name)
                        #print(layer_name, "already exist in slot", slot, layers[slot])
                    else:
                        layers.append(layer_name)
                        data.append([])
                        slot = -1
                elif line[0] == 'p':
                    pattern = r'p\s*\(' # Point up to the first (
                    pattern += r'([^,]+),' # First number in group 1
                    pattern += r'([^,]+)\)' # Second number in group 2 and )
                    pattern += r'\s*$' # Should have nothing more til the end
                    #pattern = r'p\s*\(([^,]+),([^,]+)\)\s*$'
                    m = re.search(pattern, line)
                    if not m:
                        print("\twrong syntax in point spec")
                        print(file_name,":", num, line)
                        raise Exception("point parsing error")
                    nums = [m.group(1), m.group(2)]
                    for k, n in enumerate(nums):
                        try:
                            fn = float(n)
                            l = x_min_max if k % 2 == 0 else y_min_max
                            find_min_max(l, fn)
                        except:
                            print("\twrong number presentation")
                            print(file_name,":", num, line)
                            raise Exception("unrecoginized number", n)
                    d = data[slot]
                    s = "p"
                    for n in nums:
                        s += "~~~" + n.strip()
                    d.append(s)
                elif line[0] == 'l':
                    pattern = r'l\s*\(' # Line up to the first (
                    pattern += r'([^,]+),([^,]+),([^,]+),([^,]+)\)' # Numbers
                    pattern += r'\s*$' # Should have nothing more til the end
                    #pattern = r'l\s*\(([^,]+),([^,]+),([^,]+),([^,]+)\)\s*$'
                    m = re.search(pattern, line)
                    if not m:
                        print("\twrong syntax in line spec")
                        print(file_name,":", num, line)
                        raise Exception("line parsing error")
                    nums = [m.group(1), m.group(2), m.group(3), m.group(4)]
                    for k, n in enumerate(nums):
                        try:
                            fn = float(n)
                            l = x_min_max if k % 2 == 0 else y_min_max
                            find_min_max(l, fn)
                        except:
                            print("\twrong number presentation")
                            print(file_name,":", num, line)
                            raise Exception("unrecoginized number", n)
                    d = data[slot]
                    s = "l"
                    for n in nums:
                        s += "~~~" + n.strip()
                    d.append(s)
                elif line[:3] == 'rec':
                    pattern = r'rec\s*\(' # Rectangle up to the first (
                    pattern += r'([^,]+),([^,]+),([^,]+),([^,]+)\)' # Numbers
                    pattern += r'\s*$' # Should have nothing more til the end
                    #pattern = r'rec\s*\(([^,]+),([^,]+),([^,]+),([^,]+)\)\s*$'
                    m = re.search(pattern, line)
                    if not m:
                        print("\twrong syntax in rec spec")
                        print(file_name,":", num, line)
                        raise Exception("rec parsing error")
                    nums = [m.group(1), m.group(2), m.group(3), m.group(4)]
                    for k, n in enumerate(nums):
                        try:
                            fn = float(n)
                            l = x_min_max if k % 2 == 0 else y_min_max
                            find_min_max(l, fn)
                        except:
                            print("\twrong number presentation")
                            print(file_name,":", num, line)
                            raise Exception("unrecoginized number", n)
                    d = data[slot]
                    s = "rec"
                    for n in nums:
                        s += "~~~" + n.strip()
                    d.append(s)
                elif line[:4] == 'oval':
                    pattern = r'oval\s*\(' # Oval up to the first (
                    pattern += r'([^,]+),([^,]+),([^,]+),([^,]+)\)' # Numbers
                    pattern += r'\s*$' # Should have nothing more til the end
                    #pattern = r'oval\s*\(([^,]+),([^,]+),([^,]+),([^,]+)\)\s*$'
                    m = re.search(pattern, line)
                    if not m:
                        print("\twrong syntax in oval spec")
                        print(file_name,":", num, line)
                        raise Exception("oval parsing error")
                    nums = [m.group(1), m.group(2), m.group(3), m.group(4)]
                    for k, n in enumerate(nums):
                        try:
                            fn = float(n)
                            l = x_min_max if k % 2 == 0 else y_min_max
                            find_min_max(l, fn)
                        except:
                            print("\twrong number presentation")
                            print(file_name,":", num, line)
                            raise Exception("unrecoginized number", n)
                    d = data[slot]
                    s = "oval"
                    for n in nums:
                        s += "~~~" + n.strip()
                    d.append(s)
                else:
                    raise Exception("unknown name parsing error")
                #print(file_name,":", num, line)
    return (layers, data, x_min_max[0], x_min_max[1], y_min_max[0], y_min_max[1])

def read_input(file_list):
    try:
        l, d, x_min, x_max, y_min, y_max = parse_input(file_list)
    except FileNotFoundError as er:
        print(er)
        raise Exception("Cannot read file")
    final_layer = []
    final_data = []
    for i in range(len(l)):
        if d[i]:
            final_layer.append(l[i])
            final_data.append(d[i])
    return (final_layer, final_data, x_min, x_max, y_min, y_max)

def radar_cb(widget, ctx, ctl):
    ctx.set_source_rgb(0.1, 0.1, 0.1)
    ctx.paint()
    
    world_x, world_y = ctl.world_window_anchor
    upper_left_x = world_x
    upper_left_y = world_y - ctl.zoom_size
    anchor_x = (0 - upper_left_x) * ctl.radar_size / ctl.zoom_size
    anchor_y = (0 - upper_left_y) * ctl.radar_size / ctl.zoom_size
    ctx.set_source_rgb(0.9, 0.9, 0.9)
    w, h = ctl.view_window_wh
    width = w * ctl.radar_size / ctl.zoom_size
    height = h * ctl.radar_size / ctl.zoom_size
    ctx.rectangle(anchor_x, anchor_y, width, height)
    #ctx.rectangle(50, 50, 100, 130)
    ctx.stroke()

def list_draw_cb(widget, ctx, layer_info):
    ctx.set_source_rgb(0.3, 0.3, 0.3)
    ctx.paint()
    fname, lname, cname, style, fill = layer_info.split('~~~')
    dic = {'b':'blue', 'g':'green', 'r':'red', 'c':'cyan', 'm':'magenta',
               'y':'yellow', 'w':'white', 'o':'orange', 'p':'purple',
               's':'silver', 'l':'lime', 't':'tan', 'e':'black'}
    color = dic[cname]
    dash = get_line_style(style, 2)
    rgb = Gdk.RGBA()
    rgb.parse(color)
    ctx.set_source_rgb(rgb.red, rgb.green, rgb.blue)
    ctx.move_to(0, 36)
    ctx.line_to(400, 36)
    if dash:
        ctx.set_dash(dash)
    ctx.set_line_width(2)
    ctx.stroke()
    ctx.select_font_face("Courier New", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
    ctx.set_font_size(16)
    ctx.move_to(20, 24)
    text = "{} ({})".format(lname, fname)
    text += " " + cname + style + fill
    ctx.show_text(text)

def check_cb(widget, ctl, slot):
    state = widget.get_active()
    ctl.visible_layer[slot] = state
    ctl.darea.queue_draw()

def insert_listbox(lbox, ctl):
    layer_count = len(ctl.layer)
    for i in range(layer_count):
        fixed = Gtk.Fixed()
        darea = Gtk.DrawingArea()
        darea.set_size_request(400, 40)
        layer_info = ctl.layer[i]
        darea.connect("draw", list_draw_cb, layer_info)
        fixed.put(darea, 0, 0)
        check = Gtk.CheckButton()
        check.connect("toggled", check_cb, ctl, i)
        check.set_active(True)
        fixed.put(check, 0, 0)
        lbox.insert(fixed, -1)
    
def fill_hbox1(hbox, ctl):
    ctl.darea = Gtk.DrawingArea()
    hbox.pack_start(ctl.darea, True, True, 0)
    ctl.darea.set_size_request(500, 500)
    
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    hbox.pack_end(vbox, False, False, 0)
    
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_min_content_width(ctl.radar_size)
    scrolled.set_propagate_natural_height(True)
    lbox = Gtk.ListBox()
    insert_listbox(lbox, ctl)
    scrolled.add(lbox)
    vbox.pack_start(scrolled, False, False, 0)
    
    radar = Gtk.DrawingArea()
    ctl.radar = radar
    radar.set_size_request(ctl.radar_size, ctl.radar_size)
    vbox.pack_end(radar, False, False, 0)
    radar.connect("draw", radar_cb, ctl)

def fill_hbox2(hbox, ctl):
    label = Gtk.Label(label="Zoom")
    hbox.pack_start(label, False, False, 6)
    
    button1 = Gtk.Button.new_with_label("-")
    button1.connect("clicked", zoom_out_cb, ctl)
    hbox.pack_start(button1, False, False, 2)
    
    button2 = Gtk.Button.new_with_label("+")
    button2.connect("clicked", zoom_in_cb, ctl)
    hbox.pack_start(button2, False, False, 2)

    label = Gtk.Label(label="Clicked location")
    hbox.pack_start(label, False, False, 10)
    
    entry = Gtk.Entry()
    ctl.loc_entry = entry
    entry.set_text("Not set")
    entry.set_width_chars(22)
    hbox.pack_start(entry, False, False, 0)
    
    label = Gtk.Label(label="Location:  x = 0,  y = 0")
    ctl.loc_label = label
    hbox.pack_end(label, False, False, 6)

def reset_world_anchor(ctl, new_size):
    cx, cy = [x/2 for x in ctl.view_window_wh]
    anchor_x, anchor_y = ctl.world_window_anchor
    dist_x = cx - anchor_x
    dist_y = anchor_y -cy
    dist_x /= ctl.zoom_size/new_size
    dist_y /= ctl.zoom_size/new_size
    anchor_x = cx - dist_x
    anchor_y = cy + dist_y
    ctl.world_window_anchor[0] = anchor_x
    ctl.world_window_anchor[1] = anchor_y
    
def zoom_out_cb(widget, ctl):
    new_size = ctl.zoom_size - ctl.zoom_step
    if new_size < ctl.zoom_min:
        return
    reset_world_anchor(ctl, new_size)
    ctl.zoom_size = new_size
    ctl.darea.queue_draw()
    ctl.radar.queue_draw()

def zoom_in_cb(widget, ctl):
    new_size = ctl.zoom_size + ctl.zoom_step
    if new_size > ctl.zoom_max:
        return
    reset_world_anchor(ctl, new_size)
    ctl.zoom_size = new_size
    ctl.darea.queue_draw()
    ctl.radar.queue_draw()
    
def draw_point(ctx, x, y, ctl):
    dim = ctl.resolution
    r = ctl.line_width * 2
    y = 1.0 - y
    x *= dim; y *= dim
    ctx.arc(x, y, r, 0, math.pi*2)
    ctx.fill()

def draw_line(ctx, x0, y0, x1, y1, dash, ctl):
    dim = ctl.resolution
    y0 = 1.0 - y0; y1 = 1.0 - y1
    x0 *= dim; y0 *= dim; x1 *= dim; y1 *= dim
    ctx.move_to(x0, y0)
    ctx.line_to(x1, y1)
    ctx.save()
    if dash:
        ctx.set_dash(dash)
    ctx.stroke()
    ctx.restore()

def draw_rec(ctx, x0, y0, x1, y1, dash, fill, rgb, ctl):
    dim = ctl.resolution
    w = x1 - x0; h = y1 - y0
    if w < 1.e-6 or h < 1.e-6:
        return draw_line(ctx, x0, y0, x1, y1, dash, ctl)
    y0 = 1 - y0; y1 = 1 - y1
    anchor_x = x0; anchor_y = y1
    x0, y0, x1, y1, w, h, anchor_x, anchor_y = (
        x*dim for x in [x0, y0, x1, y1, w, h, anchor_x, anchor_y])
    ctx.save()
    if dash:
        ctx.set_dash(dash)
    ctx.rectangle(anchor_x, anchor_y, w, h)
    if fill == 'f':
        ctx.fill_preserve()
        ctx.set_source_rgb(rgb.red*0.8, rgb.green*0.8, rgb.blue*0.8)
        ctx.stroke()
    elif fill == '':
        ctx.stroke()
    elif fill == 'x':
        ctx.stroke()
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
        ctx.stroke()
        ctx.move_to(x0, y1)
        ctx.line_to(x1, y0)
        ctx.stroke()
    ctx.restore()

def draw_oval(ctx, x0, y0, x1, y1, dash, fill, rgb, ctl):
    dim = ctl.resolution
    w = x1 - x0; h = y1 - y0
    if w < 1.e-6 or h < 1.e-6:
        return draw_line(ctx, x0, y0, x1, y1, dash, ctl)
    cx = (x0 + x1)/2; cy = 1-(y0 + y1)/2
    cx *= dim; cy *= dim
    if w < h:
        r = (w/2) * dim
        scale_x = 1.0
        scale_y = h/w
    else:
        r = (h/2) * dim
        scale_x = w/h
        scale_y = 1.0
    ctx.save()
    if dash:
        ctx.set_dash(dash)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(scale_x, scale_y)
    ctx.translate(-cx, -cy)
    ctx.arc(cx, cy, r, 0, math.pi*2)
    ctx.restore()
    if fill == 'f':
        ctx.fill_preserve()
        ctx.set_source_rgb(rgb.red*0.8, rgb.green*0.8, rgb.blue*0.8)
        ctx.stroke()
    elif fill == '':
        ctx.stroke()
    elif fill == 'x':
        ctx.stroke()
        ctx.move_to(x0*dim, (1-y0)*dim)
        ctx.line_to(x1*dim, (1-y1)*dim)
        ctx.stroke()
        ctx.move_to(x0*dim, (1-y1)*dim)
        ctx.line_to(x1*dim, (1-y0)*dim)
        ctx.stroke()
    ctx.restore()
    
def get_line_style(style, lunit):
    #lunit = 10
    if style == '-': # Solid line
        return []
    elif style == '--': # Dash line
        return [8*lunit, 4*lunit]
    elif style == '-.': # Dash dot
        return [8*lunit, 2*lunit, 2*lunit, 2*lunit]
    elif style == ':': # Dotted line
        return [2*lunit, 2*lunit]
    
def draw_layer(ctl):
    layer_count = len(ctl.layer)
    res = ctl.resolution
    for i in range(layer_count):
        surface = ctl.layer_surface[i]
        fname, lname, cname, style, fill = ctl.layer[i].split('~~~')
        dic = {'b':'blue', 'g':'green', 'r':'red', 'c':'cyan', 'm':'magenta',
               'y':'yellow', 'w':'white', 'o':'orange', 'p':'purple',
               's':'silver', 'l':'lime', 't':'tan', 'e':'black'}
        color = dic[cname]
        dash = get_line_style(style, 10)
        if ctl.debug:
            print("***   For layer", i)
            print(fname, lname, color, style, fill)
            print(ctl.data[i])
        rgb = Gdk.RGBA()
        rgb.parse(color)
        lctx = cairo.Context(surface)
        lctx.set_source_rgb(rgb.red, rgb.green, rgb.blue)
        lctx.set_line_width(ctl.line_width)
        for s, d in ctl.data[i]:
            #print("Shape is", s, " data is", d)
            if s == 'p':
                x, y = d
                draw_point(lctx, x, y, ctl)
            elif s == 'l':
                x0, y0, x1, y1 = d
                draw_line(lctx, x0, y0, x1, y1, dash, ctl)
            elif s == 'rec':
                x0, y0, x1, y1 = d
                draw_rec(lctx, x0, y0, x1, y1, dash, fill, rgb, ctl)
            elif s == 'oval':
                x0, y0, x1, y1 = d
                draw_oval(lctx, x0, y0, x1, y1, dash, fill, rgb, ctl)
            
        if ctl.debug:
            img_fname = 'layer{}.png'.format(i)
            img_size = ctl.png_size
            img = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_size, img_size)
            imgctx = cairo.Context(img)
            imgctx.scale(img_size/res, img_size/res)
            imgctx.set_source_surface(surface)
            imgctx.paint()
            img.write_to_png(img_fname)
    
def configure_event_cb(widget, event, ctl):
    width = widget.get_allocated_width()
    old_height = ctl.view_window_wh[1]
    height = widget.get_allocated_height()
    #print("Drawing area with width", width, "height", height)
    ctl.view_window_wh = [width, height]
    ctl.world_window_anchor[1] += height - old_height
    if ctl.layer_surface:
        return
    #print("Creating layer surface")
    layer_surface = ()
    layer_count = len(ctl.layer)
    res = ctl.resolution
    for i in range(layer_count):
        surface = widget.get_window().create_similar_surface(
            cairo.CONTENT_COLOR_ALPHA, res, res)
        #draw_layer(ctl.layer[i], ctl.data[i])
        layer_surface += (surface,)
    ctl.layer_surface = layer_surface
    draw_layer(ctl)

def expose_cb(widget, ctx, ctl):
    #print("Drawing area exposed")
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    ctl.darea.set_size_request(250, 250)
    layer_count = len(ctl.layer)
    ctx.save()
    scl = ctl.zoom_size/ctl.resolution
    world_anchor_x, world_anchor_y = ctl.world_window_anchor
    ctx.translate(world_anchor_x, world_anchor_y - ctl.zoom_size)
    ctx.scale(scl, scl)
    for i in range(layer_count):
        #print("Will transfer layer", i, "image to screen")
        if ctl.visible_layer[i]:
            surface = ctl.layer_surface[i]
            ctx.set_source_surface(surface)
            ctx.paint()
    ctx.restore()

def key_press_event_cb(widget, key, ctl):
    if key.keyval == Gdk.KEY_Right:
        ctl.world_window_anchor[0] -= 4
    elif key.keyval == Gdk.KEY_Left:
        ctl.world_window_anchor[0] += 4
    elif key.keyval == Gdk.KEY_Up:
        ctl.world_window_anchor[1] += 4
    elif key.keyval == Gdk.KEY_Down:
        ctl.world_window_anchor[1] -= 4
    else:
        pass
    ctl.darea.queue_draw()
    ctl.radar.queue_draw()

def canvas_to_data(can_x, can_y, ctl):
    dx = can_x - ctl.world_window_anchor[0]
    dy = ctl.world_window_anchor[1] - can_y
    dx = dx * ctl.max_data_range / ctl.zoom_size + ctl.x_min
    dy = dy * ctl.max_data_range / ctl.zoom_size + ctl.y_min
    return (dx, dy)

def button_press_event_cb(widget, event, ctl):
    if event.button != Gdk.BUTTON_PRIMARY:
        return
    data_x, data_y = canvas_to_data(event.x, event.y, ctl)
    ctl.loc_entry.set_text("x = {:g}  y = {:g}".format(data_x, data_y))
    
def motion_notify_event_cb(widget, event, ctl):
    if (event.state & Gdk.ModifierType.BUTTON1_MASK):
        return
    data_x, data_y = canvas_to_data(event.x, event.y, ctl)
    ctl.loc_label.set_text("Location:  x = {:g},  y = {:g}".format(data_x, data_y))
    
def connect_drawing_area_signals(ctl):
    ctl.darea.connect("configure-event", configure_event_cb, ctl)
    ctl.darea.connect("draw", expose_cb, ctl)
    ctl.darea.connect("button-press-event", button_press_event_cb, ctl)
    ctl.darea.connect("motion-notify-event", motion_notify_event_cb, ctl)
    ctl.darea.set_events(Gdk.EventMask.ALL_EVENTS_MASK)
    
class MyGtk(Gtk.Window):
    def __init__(self, c):
        super().__init__(title="2Dgraphing")
        self.ctl = c
        self.connect("destroy", Gtk.main_quit)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        
        hbox1 = Gtk.Box()
        fill_hbox1(hbox1, c)
        vbox.pack_start(hbox1, True, True, 0)
        
        hbox2 = Gtk.Box()
        fill_hbox2(hbox2, c)
        vbox.pack_start(hbox2, False, True, 0)
        
        connect_drawing_area_signals(c)
        self.connect("key-press-event", key_press_event_cb, c)
        
def run(file_list):
    if not file_list:
        print("No input file specified")
        return
    layer, data, x_min, x_max, y_min, y_max = read_input(file_list)
    #myctrl = GuiControl(layer, data, x_min, x_max, y_min, y_max, debug=True)
    myctrl = GuiControl(layer, data, x_min, x_max, y_min, y_max)
    mygtk = MyGtk(myctrl)
    mygtk.show_all()
    Gtk.main()
    
if __name__ == "__main__":
    run(sys.argv[1:])
