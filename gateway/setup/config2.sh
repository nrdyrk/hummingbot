#!/bin/bash
# init

echo
echo
echo "===============  GENERATE GATEWAY CONFIGURATION FILE(S) ==============="
echo
echo

prompt_cert_path () {
read -p "Enter the directory path for you SSL certificates (example = \"/home/user/hummingbot/certs\")>>> " CERT_PATH
if [ -d "$CERT_PATH" ]; then
    echo "SSL certificate path set as $CERT_PATH."
else 
    echo "Invalid file path, try again"
    prompt_cert_path
fi    
}
prompt_cert_path

prompt_infura_api_key () {
read -p "Enter Infura API Key (required for Ethereum node, if you do not have one, make an account at infura.io): " INFURA_KEY
echo "Infura API Key is $INFURA_KEY."
}
prompt_infura_api_key

prompt_eth_gas_station_api_key () {
read -p "Enter Eth Gas Station API Key (required for Ethereum, if you do not have one, one at https://ethgasstation.info/): " ETH_GAS_STATION_KEY
echo "Infura API Key is $ETH_GAS_STATION_KEY."
}
prompt_eth_gas_station_api_key

prompt_to_allow_telemetry () {
read -p "Do you want to enable telemetry?  [yes/no] (default = \"no\")>>> " TELEMETRY
if [[ "$TELEMETRY" == "" || "$TELEMETRY" == "No" || "$TELEMETRY" == "no" ]]
then
  echo "Telemetry disabled."
  TELEMETRY=false
elif [[ "$TELEMETRY" == "Yes" || "$TELEMETRY" == "yes" ]]
then
  echo "Telemetry enabled."
  TELEMETRY=true
else
  echo "Invalid input, try again."
  prompt_to_allow_telemetry
fi
}
prompt_to_allow_telemetry

# copy the following files
cp ./conf/samples/avalanche.yml ./conf/avalanche.yml
cp ./conf/samples/ethereum-gas-station.yml ./conf/ethereum-gas-station.yml
cp ./conf/samples/ethereum.yml ./conf/ethereum.yml
cp ./conf/samples/logging.yml ./conf/logging.yml
cp ./conf/samples/pangolin.yml ./conf/pangolin.yml
cp ./conf/samples/root.yml ./conf/root.yml
cp ./conf/samples/server.yml ./conf/server.yml
cp ./conf/samples/ssl.yml ./conf/ssl.yml
cp ./conf/samples/telemetry.yml ./conf/telemetry.yml
cp ./conf/samples/uniswap.yml ./conf/uniswap.yml

# generate the following files
