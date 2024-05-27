"""Filter the database according to various parameters"""

import contextlib

import utils
from trim import Trim

makes_list = utils.load_database("km77_cloud.json")
trims_list = [
    trim for make in makes_list for model in make.models for trim in model.trims
]
utils.clear_console()

print(f"Trims: {len(trims_list)}")


def filter_by_data(obj_list: list[Trim], key: str, value: str) -> list[Trim]:
    """Filter the trims by a given key and value"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                if specop["data"][key] == value:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_cv(obj_list: list[Trim], cv: int) -> list[Trim]:
    """Filter the trims by a given cv"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                potencia = specop["data"]["Potencia máxima"]
                if potencia == "No disponible":
                    continue
                # "170 CV / 125 kW"
                potencia = float(potencia.split("CV")[0])
                if potencia >= cv:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_accel(obj_list: list[Trim], accel: float) -> list[Trim]:
    """Filter the trims by a given acceleration"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                aceleracion = specop["data"]["Aceleración 0-100 km/h"]
                if aceleracion == "No disponible":
                    continue
                aceleracion = float(aceleracion.split("s")[0].replace(",", ".").strip())
                if aceleracion <= accel:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_cil_num(obj_list: list[Trim], cil_num: int) -> list[Trim]:
    """Filter the trims by a given number of cylinders"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                cilindros = specop["data"]["Número de cilindros"]
                if cilindros == "No disponible":
                    continue
                cilindros = int(cilindros)
                if cilindros >= cil_num:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_gears(obj_list: list[Trim], gears: int) -> list[Trim]:
    """Filter the trims by a given number of gears"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                marchas = specop["data"]["Número de velocidades"]
                if marchas in ["No disponible", "Múltiples"]:
                    continue
                marchas = int(marchas)
                if marchas >= gears:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_brake_disks(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by a given number of brake disks"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                discos_delante = specop["data"]["Tipo de frenos delanteros"]
                discos_detras = specop["data"]["Tipo de frenos traseros"]
                if (
                    "disco" in discos_delante.lower()
                    and "disco" in discos_detras.lower()
                ):
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_steering_assist(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by those with electric steering assist"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                direccion = specop["data"]["Dirección"]
                asistencia = direccion["Asistencia en función de la velocidad"]
                desmultiplicacion = direccion[
                    "Desmultiplicacion en función de la velocidad"
                ]
                if asistencia == "Sí" or desmultiplicacion == "Sí":
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_cm3(obj_list: list[Trim], cm3: int) -> list[Trim]:
    """Filter the trims by a given cm3"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                cilindrada = specop["data"]["Cilindrada"]
                if cilindrada == "No disponible":
                    continue
                cilindrada = int(cilindrada.split("cm³")[0].replace(".", ""))
                if cilindrada >= cm3:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_airfeed(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by a given airfeed"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                airfeed = specop["data"]["Alimentación"]
                if "turbo" not in airfeed.lower():
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_acc(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by having ACC"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                keys = specop["data"].keys()
                # print(keys)
                if any("crucero adapt" in key.lower() for key in keys):
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_fuel_consumption(
    obj_list: list[Trim],
    fuel_consumption: float,
) -> list[Trim]:
    """Filter the trims by a given fuel consumption"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                if "consumo" in specop["caption"].lower():
                    data_keys = specop["data"].keys()
                    # print(data_keys)
                    if any("NEDC" in key for key in data_keys):
                        consumo = specop["data"]["Consumo NEDC"]["Medio"]
                        # print(consumo)
                        consumo = float(consumo.split(" ")[0].replace(",", "."))
                        if consumo <= fuel_consumption:
                            filtered_trims.append(trim)
                            break
                    elif any("WLTP" in key for key in data_keys):
                        consumo = specop["data"]["Consumo WLTP"]["Combinado"]
                        consumo = float(consumo.split(" ")[0].replace(",", "."))
                        if consumo <= fuel_consumption:
                            filtered_trims.append(trim)
                            break

    return filtered_trims


def filter_by_keyless(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by keyless"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                keys = specop["data"].keys()
                if any("sin llave" in key.lower() for key in keys):
                    filtered_trims.append(trim)
                    break

    return filtered_trims


def filter_by_height(obj_list: list[Trim], height: float) -> list[Trim]:
    """Filter the trims by a given height"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                altura = specop["data"]["Altura"]
                if altura == "No disponible":
                    continue
                altura = float(altura.split("mm")[0].replace(".", ""))
                if altura >= height:
                    filtered_trims.append(trim)
                    break
    return filtered_trims


def filter_by_electric_seat(obj_list: list[Trim]) -> list[Trim]:
    """Filter the trims by electric seat"""
    filtered_trims = []
    for trim in obj_list:
        for specop in trim.specs + trim.options:
            with contextlib.suppress(KeyError):
                keys = specop["data"].keys()
                if any("delanteros eléctricos" in key.lower() for key in keys):
                    filtered_trims.append(trim)
                    break

    return filtered_trims


gas_list = filter_by_data(trims_list, "Combustible", "Gasolina")
diesel_list = filter_by_data(trims_list, "Combustible", "Gasóleo")
candidates_list = gas_list + diesel_list

print(f"ICE: {len(candidates_list)}")

candidates_list = filter_by_data(candidates_list, "Caja de cambios", "Automático")
print(f"Automatic: {len(candidates_list)}")

# candidates_list = filter_by_cv(candidates_list, 115)
# print(f"Power: {len(candidates_list)}")

candidates_list = filter_by_accel(candidates_list, 9)
print(f"Acceleration: {len(candidates_list)}")

# candidates_list = filter_by_cil_num(candidates_list, 4)
# print(f"Cylinder: {len(candidates_list)}")

# candidates_list = filter_by_gears(candidates_list, 6)
# print(f"Gears: {len(candidates_list)}")

candidates_list = filter_by_brake_disks(candidates_list)
print(f"Brakes: {len(candidates_list)}")

# candidates_list = filter_by_steering_assist(candidates_list)
# print(f"Steering: {len(candidates_list)}")

# candidates_list = filter_by_cm3(candidates_list, 1550)
# print(f"cm3: {len(candidates_list)}")

# candidates_list = filter_by_airfeed(candidates_list)
# print(f"Naturally Aspirated: {len(candidates_list)}")

candidates_list = filter_by_data(
    candidates_list,
    "Número de plazas",
    "5",
) + filter_by_data(candidates_list, "Número de plazas", "4")
print(f"Seats: {len(candidates_list)}")

# candidates_list = filter_by_acc(candidates_list)
# print(f"ACC: {len(candidates_list)}")

candidates_list = filter_by_fuel_consumption(candidates_list, 5)
print(f"Fuel Consumption: {len(candidates_list)}")

candidates_list = filter_by_height(candidates_list, 1500)
print(f"Height: {len(candidates_list)}")

candidates_list = filter_by_keyless(candidates_list)
print(f"Keyless: {len(candidates_list)}")

candidates_list = filter_by_electric_seat(candidates_list)
print(f"Electric Seat: {len(candidates_list)}")

print()
print("Results:")
for trim in candidates_list:
    print(f"{trim.name}" + f"\n\t{trim.production}" + f"\n\t{trim.children_url}\n")
