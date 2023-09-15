from copy import deepcopy


basic_element = {
    "nch": "m",
    "pch": "m",
    "capacitor": "c",
    "resistor": "r",
    "iprobe": "x",
}


class Device(object):
    def __init__(self, name, model, parameters, label, level):
        self.name = name
        self.model = model
        self.parameters = parameters
        self.level = level
        self.pins = []
        self.parent_ckt = None
        self.label = label
        self.edge_weight = list(range(8))  # (d, g, s, b, r1, r2, c1, c2)

    def add_pins(self, pins):
        self.pins = pins


class SubCkt(object):
    def __init__(self, name, level, nets, io_nets, internal_nets):
        self.name = name
        self.level = level
        self.devices = []
        self.subckts = []
        self.nets = nets
        self.io_nets = io_nets
        self.corresponding_instance_nets = []
        self.internal_nets = internal_nets
        self.parent_ckt = None
        self.allDeviceName2Id = {}
        self.allSubcktName2Id = {}

    def add_device(self, device):
        if device.name not in self.allDeviceName2Id.keys():
            self.devices.append(device)
            self.allDeviceName2Id[device.name] = len(self.devices)

    def add_subckt(self, subckt):
        if subckt.name not in self.allSubcktName2Id.keys():
            self.subckts.append(subckt)
            self.allSubcktName2Id[subckt.name] = len(self.subckts)


class Ckt(object):
    def __init__(self, name, level, nets, io_nets, internal_nets):
        self.name = name
        self.type = "Top"
        self.level = level
        self.max_level = 0
        self.devices = []
        self.subckts = []
        self.parent_ckt = None
        self.nets = nets
        self.io_nets = io_nets
        self.internal_nets = internal_nets
        self.corresponding_instance_nets = None
        self.allDeviceName2Id = {}
        self.allSubcktName2Id = {}

    def add_device(self, device):
        if device.name not in self.allDeviceName2Id.keys():
            self.devices.append(device)
            self.allDeviceName2Id[device.name] = len(self.devices)
            if device.level > self.max_level:
                self.max_level = device.level

    def add_subckt(self, subckt):
        if subckt.name not in self.allSubcktName2Id.keys():
            self.subckts.append(subckt)
            self.allSubcktName2Id[subckt.name] = len(self.subckts)


def is_device(netlist, inst):
    for name, ckt in netlist.subckts.items():
        if name == inst.model:
            return (False, ckt)
    return (True, None)


def hiera_circuit(netlist, topckt, subckt, inst, name_prefix, level):
    isd, ckt = is_device(netlist, inst)
    if isd:
        if inst.model in basic_element:
            device = Device(
                name=name_prefix,
                model=inst.model,
                parameters=inst.params,
                label=inst.label,
                level=level + 1,
            )
        else:
            Exception("Not support for this type device")
        device.add_pins(deepcopy(inst.terminals))
        device.parent_ckt = subckt
        subckt.add_device(device)
        topckt.add_device(device)
        return
    else:
        new_subckt = SubCkt(
            name=name_prefix,
            level=level + 1,
            nets=ckt.nets,
            io_nets=ckt.terminals,
            internal_nets=ckt.internal_nets,
        )
        new_subckt.parent_ckt = subckt
        new_subckt.corresponding_instance_nets = inst.terminals
        subckt.add_subckt(new_subckt)
        topckt.add_subckt(new_subckt)
        for inst in ckt.components:
            hiera_circuit(
                netlist,
                topckt,
                new_subckt,
                inst,
                name_prefix + "_" + inst.name,
                level=level + 1,
            )


def build_ckt(netlist):
    for i, ckt in netlist.subckts.items():
        if ckt.typeof == "topcircuit":
            TopCkt = Ckt(
                name=ckt.name,
                level=0,
                nets=ckt.nets,
                io_nets=ckt.terminals,
                internal_nets=ckt.internal_nets,
            )
            for inst in ckt.components:
                hiera_circuit(
                    netlist,
                    TopCkt,
                    TopCkt,
                    inst,
                    TopCkt.name + "_" + inst.name,
                    level=0,
                )

    print("start flatten")
    flatten_nets(TopCkt)

    return TopCkt


def flatten_nets(topckt):
    for dev in topckt.devices:
        if dev.parent_ckt.level == 0:
            continue
        for i, pin in enumerate(dev.pins):
            sub_ckt = dev.parent_ckt
            find_net = pin
            if sub_ckt.parent_ckt == None:
                dev.pins[i] = find_net
            else:
                while sub_ckt.parent_ckt != None:
                    if find_net in sub_ckt.internal_nets:
                        dev.pins[i] = (
                            f"{sub_ckt.name}_{find_net}" if find_net != "0" else "0"
                        )
                        break
                    else:
                        loc = sub_ckt.io_nets.index(find_net)
                        find_net = sub_ckt.corresponding_instance_nets[loc]
                        sub_ckt = sub_ckt.parent_ckt
                # rename
                if sub_ckt.parent_ckt == None:
                    dev.pins[i] = find_net
    print("flatten done")
