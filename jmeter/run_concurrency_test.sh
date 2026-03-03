#!/bin/bash

# Summit 2026 Interactive Lab - JMeter Concurrency Test Runner
# Usage: ./run_concurrency_test.sh [WAREHOUSE_NAME]

set -e

WAREHOUSE=${1:-SUMMIT_INT_WH}
REPORT_DIR="results_${WAREHOUSE}_$(date +%Y%m%d_%H%M%S)"

echo "================================================================================"
echo "  Snowflake Concurrency Test - ${WAREHOUSE}"
echo "================================================================================"
echo ""
echo "Configuration:"
echo "  Warehouse     : ${WAREHOUSE}"
echo "  Threads       : 50 concurrent users"
echo "  Duration      : 30 seconds"
echo "  Report Dir    : ${REPORT_DIR}"
echo ""
echo "================================================================================"
echo ""

# Check if Snowflake JDBC driver exists
JDBC_JAR="./snowflake-jdbc.jar"
if [ ! -f "$JDBC_JAR" ]; then
    echo "ERROR: Snowflake JDBC driver not found at $JDBC_JAR"
    echo ""
    echo "Download it with:"
    echo "  curl -L -o snowflake-jdbc.jar https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.16.1/snowflake-jdbc-3.16.1.jar"
    echo ""
    exit 1
fi

# Find JMeter lib directory and copy driver there
JMETER_HOME=$(dirname $(dirname $(which jmeter 2>/dev/null || echo "/usr/local/bin/jmeter")))
JMETER_LIB="$JMETER_HOME/libexec/lib"

# Try common JMeter lib locations
if [ ! -d "$JMETER_LIB" ]; then
    JMETER_LIB="$JMETER_HOME/lib"
fi

if [ -d "$JMETER_LIB" ]; then
    echo "Installing JDBC driver to JMeter lib directory: $JMETER_LIB"
    cp "$JDBC_JAR" "$JMETER_LIB/" 2>/dev/null || {
        echo "WARNING: Could not copy to JMeter lib. You may need sudo:"
        echo "  sudo cp $JDBC_JAR $JMETER_LIB/"
        echo ""
        echo "Or set JMETER_HOME and run again"
        echo ""
    }
else
    echo "WARNING: Could not locate JMeter lib directory"
    echo "Please manually copy snowflake-jdbc.jar to your JMeter lib directory"
    echo ""
fi

# Check for required environment variables
if [ -z "$SNOWFLAKE_ACCOUNT" ] || [ -z "$SNOWFLAKE_PRIVATE_KEY_FILE" ]; then
    echo "ERROR: Missing required environment variables"
    echo ""
    echo "Please set:"
    echo "  export SNOWFLAKE_ACCOUNT=your_account"
    echo "  export SNOWFLAKE_PRIVATE_KEY_FILE=/path/to/rsa_key.p8"
    echo ""
    echo "Optionally set (defaults to ARCADE_STREAMING_USER):"
    echo "  export SNOWFLAKE_USER=ARCADE_STREAMING_USER"
    echo ""
    exit 1
fi

# Default to ARCADE_STREAMING_USER if not specified
SNOWFLAKE_USER=${SNOWFLAKE_USER:-ARCADE_STREAMING_USER}

# Run JMeter test with Java module opens for Arrow
export JVM_ARGS="--add-opens=java.base/java.nio=ALL-UNNAMED"

jmeter -n -t concurrency_test.jmx \
    -JSNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
    -JSNOWFLAKE_USER="$SNOWFLAKE_USER" \
    -JSNOWFLAKE_PRIVATE_KEY_FILE="$SNOWFLAKE_PRIVATE_KEY_FILE" \
    -JSNOWFLAKE_WAREHOUSE="$WAREHOUSE" \
    -l "${REPORT_DIR}/results.jtl" \
    -e -o "${REPORT_DIR}"

echo ""
echo "================================================================================"
echo "  Test Complete!"
echo "================================================================================"
echo ""
echo "View results:"
echo "  Summary     : cat ${REPORT_DIR}/statistics.json"
echo "  HTML Report : open ${REPORT_DIR}/index.html"
echo ""
echo "Key metrics from results.jtl:"
awk -F',' 'NR>1 {sum+=$2; count++; if($2>max)max=$2; if(min=="" || $2<min)min=$2} 
    END {print "  Total Queries : " count; 
         print "  Avg Latency   : " int(sum/count) " ms"; 
         print "  Min Latency   : " min " ms"; 
         print "  Max Latency   : " max " ms"}' "${REPORT_DIR}/results.jtl"
echo ""
echo "================================================================================"
