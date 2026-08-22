##########################################################
#
# Script: qihe.py
# Author: Jani Hirvinen aka jpkh
# Contact: [Use GitHub issues for questions and suggestions]
# Repository: https://github.com/jpkh/ki_qihe
#
# Date: 2024-04-07
# Version: 1.0
#
# Description:
# This script handles the generation of machine-readable files for QIHE PnP machines
# based on the PCB design data provided.
#
# Works:
#  - Windows/Cywin
#  - Linux
#  - MacOS
#


import pcbnew  # type: ignore
import csv
import os
import re
from threading import Thread
from .functions import create_default_mapping_file
from .config import def_CompopentMapping, def_top_fileext, def_bottom_fileext
from .log_util import log_message
import traceback

# Class to handle the QIHE process


class QiHeProcess(Thread):
    def __init__(self, options, log_activity):
        Thread.__init__(self)
        self.options = options
        self.log_activity = log_activity
        self.verbosity_level = options.get("verbosity_level", 0)
        
        # NEW: value+size → (nozzle, feeder)
        self.mapping_by_size = {}

    # Run the QIHE process
    def run(self):
        try:
            self.log_activity("Starting QiHeProcess run method")
            board = pcbnew.GetBoard()
            if not board:
                self.log_activity("No active board found. Please ensure a board is loaded in KiCad.")
                return
            self.log_activity("Board loaded successfully.")

            component_mapping_file = self.get_mapping_file_path()
            self.log_activity(f"Using component mapping file at: {component_mapping_file}")

            self.component_mapping, self.exclude_patterns, self.priority_patterns = self.load_component_mapping(
                component_mapping_file, self.log_activity)
            self.generate_qihe_files()
        except Exception as e:
            self.log_error(e)

    # Log an activity message
    def log_error(self, message_or_exception):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        log_file = os.path.join(plugin_dir, "save_restore_error.log")
        error_message = f"Unhandled exception in QiHeProcess: {repr(message_or_exception)}"
        with open(log_file, "a") as f:
            f.write(error_message + "\n" + traceback.format_exc() + "\n")
        self.log_activity(error_message)  # Also log to GUI activity log

    # Get the path to the mapping file
    def get_mapping_file_path(self):
        mapping_location = self.options.get("mapping_location", 0)  # Default to 0 if not set
        mapping_file_name = self.options.get("mapping_file_name", def_CompopentMapping)
        if mapping_location == 0:  # Plugin Folder
            plugin_dir = os.path.dirname(os.path.realpath(__file__))
            return os.path.join(plugin_dir, mapping_file_name)
        else:  # pcbnew Working Folder
            board_dir = os.path.dirname(pcbnew.GetBoard().GetFileName())
            return os.path.join(board_dir, mapping_file_name)

    # Generate the QIHE files
    def generate_qihe_files(self):
        board_file_path = pcbnew.GetBoard().GetFileName()
        board_base_name = os.path.splitext(os.path.basename(board_file_path))[0]
        board_dir = os.path.dirname(board_file_path)
        top_fileext = self.options.get("top_fileext", def_top_fileext)
        bottom_fileext = self.options.get("bottom_fileext", def_bottom_fileext)
        output_file_top = os.path.join(board_dir, f"{board_base_name}_{top_fileext}.csv")
        output_file_bottom = os.path.join(board_dir, f"{board_base_name}_{bottom_fileext}.csv")
        self.log_activity(f"Generating QIHE files:\n ")
        #self.log_activity(f"- {output_file_top}\n")
        #self.log_activity(f"- {output_file_bottom}\n")

        X_Offset = self.options.get("X_Offset", 0)
        Y_Offset = self.options.get("Y_Offset", 0)

        # Retrieve component mapping and patterns again in case they've been updated
        component_mapping, exclude_patterns, priority_patterns = self.load_component_mapping(
            self.get_mapping_file_path(), self.log_activity)

        # Check layer processing options
        process_top_layer = self.options.get('process_top_layer', False)
        process_bottom_layer = self.options.get('process_bottom_layer', False)

        if not process_top_layer and not process_bottom_layer:
            self.log_activity("No layer(s) selected.")
            return  # Stop further processing as no layers are selected

        if process_top_layer:
            self.write_qihe_file(output_file_top,
                                 pcbnew.GetBoard().GetFootprints(),
                                 pcbnew.F_Cu,
                                 X_Offset, Y_Offset,
                                 self.component_mapping,
                                 self.exclude_patterns,
                                 self.priority_patterns)
            #self.log_activity(f"- ## {output_file_top}\n")
            self.log_activity("Processed top layer.")

        if process_bottom_layer:
            self.write_qihe_file(output_file_bottom,
                                 pcbnew.GetBoard().GetFootprints(),
                                 pcbnew.B_Cu,
                                 X_Offset, Y_Offset,
                                 self.component_mapping,
                                 self.exclude_patterns,
                                 self.priority_patterns)
            #self.log_activity(f"-# {output_file_bottom}\n")
            self.log_activity("Processed bottom layer.")

    # Check if the module should be excluded based on exclude_patterns
    def is_excluded(self, mod, exclude_patterns):
        """Check if the module should be excluded based on exclude_patterns."""
        # value = mod.GetValue().strip().lower()  # Normalize the value for case-insensitive comparison
        for pattern in exclude_patterns:
            if re.search(pattern, mod.GetValue(), re.IGNORECASE):
                if self.verbosity_level >= 3:
                    self.log_activity(f"Excluding {mod.GetReference()} based on pattern: {pattern}")
                return True
        return False

    # Check if the module is a priority based on priority_patterns
    def is_priority(self, mod, priority_patterns):
        """Check if the module is a priority based on priority_patterns."""
        # value = mod.GetValue().strip().lower()  # Normalize the value for case-insensitive comparison
        for pattern in priority_patterns:
            if re.search(pattern, mod.GetValue(), re.IGNORECASE):
                if self.verbosity_level >= 3:
                    self.log_activity(f"Prioritizing {mod.GetReference()} based on pattern: {pattern}")
                return True
        return False

    # Get the sort key for the module
    def get_sort_key(self, mod):
        """Sort modules by the component value, normalized for case insensitivity."""
        key = mod.GetValue().split()[0]
        if self.verbosity_level >= 3:
            self.log_activity(f"Sort key for {mod.GetReference()} is {key}")
        return key
        # return mod.GetValue().strip().lower()
        #return mod.GetValue().split()[0]

    # Load the component mapping from the file
    def load_component_mapping(self, filename, log_activity):
        # Metric→Imperial for common KiCad tokens
        METRIC_TO_IMPERIAL = {
            "1005": "0402",
            "1608": "0603",
            "2012": "0805",
            "3216": "1206",
            "3225": "1210",
            "4532": "1812",
            "5025": "2010",
            "6332": "2512",
        }
        VALID_IMPERIAL = {"01005","0201","0402","0603","0805","1206","1210","1812","2010","2512"}

        def _norm_size(s):
            if not s:
                return ""
            s = s.strip().upper()
            # try imperial directly
            if s in VALID_IMPERIAL:
                return s
            # try metric digits (e.g. "1608")
            m = re.fullmatch(r"\d{4}", s)
            if m:
                return METRIC_TO_IMPERIAL.get(s, "")
            return ""

        if not os.path.exists(filename):
            create_default_mapping_file(filename, log_activity)
            log_activity(f"Default mapping file created at: {filename}")

        mapping = {}
        exclude_patterns = []
        priority_patterns = []
        # reset size map every load
        self.mapping_by_size = {}

        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue  # Skip empty lines and comments

                parts = line.split(',')
                if len(parts) < 3:
                    continue

                prefix, param1, param2 = parts[0].strip(), parts[1].strip(), parts[2].strip()

                if prefix == "E":
                    exclude_patterns.extend(p.strip() for p in param2.split(':') if p.strip())
                    if self.verbosity_level >= 1:
                        log_activity(f"Exclusion patterns loaded: {param2}")

                elif prefix == "P":
                    priority_patterns.extend(p.strip() for p in param2.split(':') if p.strip())
                    if self.verbosity_level >= 1:
                        log_activity(f"Priority patterns loaded: {param2}")

                else:
                    # Component mapping line: "<nozzle>, <feeder[:SIZE]>, <value[:aliases]>"
                    nozzle = prefix
                    feeder_raw = param1
                    feeder, size_tag = feeder_raw, ""

                    # Support "L14:0402", "T12:0603", or metric like "L9:1608"
                    if ':' in feeder_raw:
                        feeder, size_tag = feeder_raw.split(':', 1)
                        size_tag = _norm_size(size_tag)  # your normalizer

                    for comp in param2.split(':'):
                        comp_key = comp.strip()
                        if not comp_key:
                            continue

                        if size_tag:
                            # size-specific only (do NOT touch generic map)
                            self.mapping_by_size[(comp_key.lower(), size_tag)] = (nozzle, feeder.strip())
                        else:
                            # pure generic mapping
                            mapping[comp_key] = (nozzle, feeder.strip())

                        if self.verbosity_level >= 1:
                            tag = f" size={size_tag}" if size_tag else ""
                            log_activity(f"Component mapping: '{comp_key}' → N:{nozzle}, F:{feeder.strip()}{tag}")


        if self.verbosity_level >= 1:
            log_activity(f"Final mapping count: {len(mapping)}; size-specific: {len(self.mapping_by_size)}")

        return mapping, exclude_patterns, priority_patterns

    
    def get_fiducial_origin(self):
        """Retrieve the origin based on a custom fiducial marked as FIDORIG, and return a status message."""
        for module in pcbnew.GetBoard().GetFootprints():
            if module.GetReference().startswith("FIDORIG"):
                origin_message = f"Using {module.GetReference()} at {module.GetPosition()} as origin."
                self.log_activity(origin_message)
                return module.GetPosition(), origin_message
        # Log and use page origin if FIDORIG is not found
        origin_message = "\n!!!! WARNING !!!! FIDORIG fiducial not found. Using Page coordinates instead. \n"
        self.log_activity(origin_message)
        return pcbnew.wxPoint(0, 0), origin_message



    def write_qihe_file(self, filename, footprints, layer, X_Offset, Y_Offset,
                        component_mapping, exclude_patterns, priority_patterns):
        MAXNAMELENGTH = 10

        SMD_SIZE_RE = re.compile(r'\b(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)\b', re.IGNORECASE)
        METRIC_TO_IMPERIAL = {
            "1005": "0402",
            "1608": "0603",
            "2012": "0805",
            "3216": "1206",
            "3225": "1210",
            "4532": "1812",
            "5025": "2010",
            "6332": "2512",
        }
        METRIC_RE = re.compile(r'(?<!\d)(?:_|-)?(1005|1608|2012|3216|3225|4532|5025|6332)(?:Metric)?(?!\d)', re.IGNORECASE)

        def _s(x):
            try: return str(x)
            except: return ""

        def _get_fp_strings(mod):
            s = []
            try:
                fpid = mod.GetFPID()
                if hasattr(fpid, "GetFootprintName"):
                    s.append(_s(fpid.GetFootprintName()))
                if hasattr(fpid, "GetLibItemName"):
                    s.append(_s(fpid.GetLibItemName()))
                if not s:
                    s.append(_s(fpid))
            except:
                pass
            return " ".join(s)

        def _detect_size(mod):
            val = _s(mod.GetValue())
            m = SMD_SIZE_RE.search(val)
            if m:
                return m.group(1).upper()[:MAXNAMELENGTH]
            fp_str = _get_fp_strings(mod)
            m = SMD_SIZE_RE.search(fp_str)
            if m:
                return m.group(1).upper()[:MAXNAMELENGTH]
            m = METRIC_RE.search(fp_str)
            if m:
                metric = m.group(1)
                imp = METRIC_TO_IMPERIAL.get(metric, "")
                if imp:
                    return imp[:MAXNAMELENGTH]
            return ""

        origin, origin_message = self.get_fiducial_origin()  # Fetch the origin point
        try:
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Designator", "NozzleNum", "StackNum", "Mid X", "Mid Y",
                                 "Rotation", "Height", "Speed", "Vision", "Check", "Explanation"])

#                writer.writerow("")
                priority_footprints = []
                mapped_footprints = []
                unmapped_footprints = []
                excluded_by_pattern = []
                excluded_by_attribute = []

                filtered_footprints = [mod for mod in footprints if mod.GetLayer() == layer]

                for mod in filtered_footprints:
                    debug_info = f"Processing {_s(mod.GetReference())}: Layer={mod.GetLayer()}, Value='{_s(mod.GetValue())}'"

                    # Excluded by attributes?
                    if mod.GetAttributes() & (pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM):
                        excluded_by_attribute.append(mod)
                        if self.verbosity_level >= 2:
                            self.log_activity(debug_info + " - Excluded by attribute")
                        continue

                    # Excluded by pattern?
                    if self.is_excluded(mod, exclude_patterns):
                        excluded_by_pattern.append(mod)
                        if self.verbosity_level >= 2:
                            self.log_activity(debug_info + " - Excluded by pattern")
                        continue

                    # Priority?
                    if self.is_priority(mod, priority_patterns):
                        priority_footprints.append(mod)
                        if self.verbosity_level >= 2:
                            self.log_activity(debug_info + " - Priority")
                        continue

                    # --- NEW: size-aware grouping so size-mapped parts appear in the mapped block ---
                    value = _s(mod.GetValue())
                    size  = _detect_size(mod)
                    size_key = (value.lower(), size) if size else None

                    if size_key and size_key in self.mapping_by_size:
                        mapped_footprints.append(mod)
                        if self.verbosity_level >= 2:
                            nozzle_num, feeder_location = self.mapping_by_size[size_key]
                            self.log_activity(debug_info + f" - Mapped (size) N:{nozzle_num}, F:{feeder_location}, Size:{size}")
                    elif value in component_mapping:
                        mapped_footprints.append(mod)
                        if self.verbosity_level >= 2:
                            nozzle_num, feeder_location = component_mapping[value]
                            self.log_activity(debug_info + f" - Mapped (generic) N:{nozzle_num}, F:{feeder_location}")
                    else:
                        unmapped_footprints.append(mod)
                        if self.verbosity_level >= 2:
                            self.log_activity(debug_info + " - Unmapped")
                    # -------------------------------------------------------------------------------


                for group in [priority_footprints, mapped_footprints, unmapped_footprints]:
                    group.sort(key=self.get_sort_key)
                    for mod in group:
                        mid_x = ((mod.GetPosition().x - origin.x) / 1000000.0)
                        mid_y = ((mod.GetPosition().y - origin.y) / 1000000.0)
                        rotation = (mod.GetOrientationDegrees() + 270) % 360

                        value = _s(mod.GetValue())
                        ref = _s(mod.GetReference())
                        size = _detect_size(mod)

                        # --- size-aware lookup first, fallback to legacy mapping ---
                        nozzle_num, stack_num = ("1/2", "None")
                        if size:
                            hit = self.mapping_by_size.get((value.lower(), size))
                            if hit:
                                nozzle_num, stack_num = hit
                            elif value in component_mapping:
                                nozzle_num, stack_num = component_mapping[value]
                        else:
                            if value in component_mapping:
                                nozzle_num, stack_num = component_mapping[value]
                        # ----------------------------------------------------------


                        explanation = f"{ref} {value}" + (f" {size}" if size else "")
                        if mod in priority_footprints:
                            explanation = "PRIO " + explanation

                        writer.writerow([
                            ref,
                            nozzle_num,
                            stack_num,
                            f"{mid_y:.2f}",
                            f"{mid_x:.2f}",
                            f"{rotation:.2f}",
                            "0.00",
                            "100",
                            "Quick",  # We run vision now constantly
                            "Vision",
                            explanation
                        ])

                layer_name = "Top layer" if layer == pcbnew.F_Cu else "Bottom layer"
                self.log_activity("\n###########################")
                self.log_activity(f"{layer_name}:")
                self.log_activity(f"- Total components: {len(filtered_footprints)}")
                self.log_activity(f"- Mapped components: {len(mapped_footprints)}")
                self.log_activity(f"- Priority components: {len(priority_footprints)}")
                self.log_activity(f"- Excluded (pattern/attribute): {len(excluded_by_pattern)} / {len(excluded_by_attribute)}")
                self.log_activity(f"- Unmapped components: {len(unmapped_footprints)}")
                self.log_activity(origin_message)

                writer.writerow([])
                writer.writerow(["Puzzle"])
                for _ in range(8):
                    writer.writerow(["0.00"])
                    writer.writerow([])
                writer.writerow([])
                writer.writerow([])

                self.log_activity(f"Successfully written to file: {filename}")

        except Exception as e:
            self.log_activity(f"Error writing to file {filename}: {str(e)}")

# End qihe.py
