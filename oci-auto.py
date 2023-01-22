import os
import oci
import logging
import time
import sys
import requests
from decouple import config

LOG_FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("oci.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

#####################################      SCRIPT SETTING, CHANGE THIS        #########################################
# Script Setting, change this (Each VM.Standard.A1.Flex ocpus = 6 GB memroy)
# instance_type = "VM.Standard.A1.Flex"
# OCI API_KEY and other parametter: https://github.com/hitrov/oci-arm-host-capacity (intercept request from web console)
requesting=0
ocpus = int(config('OCPUS'))
memory_in_gbs = ocpus * 6
wait_s_for_retry = int(config('WAIT_S_FOR_RETRY'))
instance_display_name = config('INSTANCE_DISPLAY_NAME')
compartment_id = config('COMPARTMENT_ID')
domain = config('DOMAIN')
image_id = config('IMAGE_ID')
subnet_id = config('SUBNET_ID')

ssh_key = config('SSH_KEY')

#######################################################################################################################
logging.info("#####################################################")
logging.info("Script to spawn VM.Standard.A1.Flex instance")


message = f'Start spawning instance VM.Standard.A1.Flex - {ocpus} ocpus - {memory_in_gbs} GB'
logging.info(message)
print(f"{message}\n\n\n\n") 

# Loading config file
logging.info("Loading OCI config")
config = oci.config.from_file(file_location="./config")

# Initialize service client
logging.info("Initialize service client with default config file")
to_launch_instance = oci.core.ComputeClient(config)


message = f"Instance to create: VM.Standard.A1.Flex - {ocpus} ocpus - {memory_in_gbs} GB"
logging.info(message)
print(f"{message}\n\n\n\n") 

###########################       Check current existing instance(s) in account         ##############################
logging.info("Check current instances in account")
logging.info(
    "Note: Free upto 4xVM.Standard.A1.Flex instance, total of 4 ocpus and 24 GB of memory")
current_instance = to_launch_instance.list_instances(
    compartment_id=compartment_id)
response = current_instance.data
# oci.core.models.InstanceShapeConfig
# print(type(response[0]))
total_ocpus = total_memory = _A1_Flex = 0
instance_names = []
if response:
    logging.info(f"{len(response)} instance(s) found!")
    for instance in response:
        logging.info(f"{instance.display_name} - {instance.shape} - {int(instance.shape_config.ocpus)} ocpu(s) - {instance.shape_config.memory_in_gbs} GB(s) | State: {instance.lifecycle_state}")
        instance_names.append(instance.display_name)
        if instance.shape == "VM.Standard.A1.Flex" and instance.lifecycle_state not in ("TERMINATING", "TERMINATED"):
            _A1_Flex += 1
            total_ocpus += int(instance.shape_config.ocpus)
            total_memory += int(instance.shape_config.memory_in_gbs)

    message = f"Current: {_A1_Flex} active VM.Standard.A1.Flex instance(s) (including RUNNING OR STOPPED)"
    logging.info(message)
    print(f"{message}\n\n\n\n") 
else:
    logging.info(f"No instance(s) found!")


message = f"Total ocpus: {total_ocpus} - Total memory: {total_memory} (GB) || Free {4-total_ocpus} ocpus - Free memory: {24-total_memory} (GB)"
logging.info(message)
print(f"{message}\n\n\n\n") 


# Pre-check to verify total resource of current VM.Standard.A1.Flex (max 4 ocpus/24GB ram)
if total_ocpus + ocpus > 4 or total_memory + memory_in_gbs > 24:
    message = "Total maximum resource exceed free tier limit (Over 4 ocpus/24GB total). **SCRIPT STOPPED**"
    logging.critical(message)
    print(f"{message}\n\n\n\n") 
    sys.exit()

# Check for duplicate display name
if instance_display_name in instance_names:
    message = f"Duplicate display name: >>>{instance_display_name}<<< Change this! **SCRIPT STOPPED**"
    logging.critical(message)
    print(f"{message}\n\n\n\n") 
    sys.exit()

message = f"Precheck pass! Create new instance VM.Standard.A1.Flex: {ocpus} opus - {memory_in_gbs} GB"
logging.info(message)
print(f"{message}\n\n\n\n") 
######################################################################################################################

# Instance-detail
instance_detail = oci.core.models.LaunchInstanceDetails(
    metadata={
        "ssh_authorized_keys": ssh_key
    },
    availability_domain=domain,
    shape='VM.Standard.A1.Flex',
    compartment_id=compartment_id,
    display_name=instance_display_name,
    source_details=oci.core.models.InstanceSourceViaImageDetails(
        source_type="image", image_id=image_id),
    create_vnic_details=oci.core.models.CreateVnicDetails(
        assign_public_ip=False, subnet_id=subnet_id, assign_private_dns_record=True),
    agent_config=oci.core.models.LaunchInstanceAgentConfigDetails(
        is_monitoring_disabled=False,
        is_management_disabled=False,
        plugins_config=[oci.core.models.InstanceAgentPluginConfigDetails(
            name='Vulnerability Scanning', desired_state='DISABLED'), oci.core.models.InstanceAgentPluginConfigDetails(name='Compute Instance Monitoring', desired_state='ENABLED'), oci.core.models.InstanceAgentPluginConfigDetails(name='Bastion', desired_state='DISABLED')]
    ),
    defined_tags={},
    freeform_tags={},
    instance_options=oci.core.models.InstanceOptions(
        are_legacy_imds_endpoints_disabled=False),
    availability_config=oci.core.models.LaunchInstanceAvailabilityConfigDetails(
        recovery_action="RESTORE_INSTANCE"),
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
        ocpus=ocpus, memory_in_gbs=memory_in_gbs)
)

#######################################      Main loop - program        ####################################################
# Script try to send request each $wait_s_for_retry seconds until success
to_try = True
while to_try:
    requesting+=1
    try:
        to_launch_instance.launch_instance(instance_detail)
        to_try = False
        message = 'Success! Edit vnic to get public ip address'
        logging.info(message)
        print(f"{message}\n\n\n\n") 
        # print(to_launch_instance.data)
        session.close()
    except oci.exceptions.ServiceError as e:
        if e.status == 500:
            # Out of host capacity.
            message = f"Request number: {requesting} - {e.message} Retry in {wait_s_for_retry}s"
            #print(f"{message}\n\n\n\n") 
        else:
            message = f"{e} Retry in {wait_s_for_retry}s"
            print(f"{message}\n\n\n\n") 
        logging.info(message)
        time.sleep(wait_s_for_retry)
    except Exception as e:
        message = f"{e} Retry in {wait_s_for_retry}s"
        logging.info(message)
        print(f"{message}\n\n\n\n") 
        time.sleep(wait_s_for_retry)
    except KeyboardInterrupt:
        session.close()
        sys.exit()