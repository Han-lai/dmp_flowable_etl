FROM clickhouse/clickhouse-server:25.8.18.1

# Install unixodbc and Microsoft ODBC Driver 18 for SQL Server
RUN apt-get update && apt-get install -y curl apt-transport-https gnupg2 unixodbc \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && printf "[ODBC Driver 18 for SQL Server]\nDescription=Microsoft ODBC Driver 18 for SQL Server\nDriver=/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.6.so.1.1\nUsageCount=1\n" > /etc/odbcinst.ini

# Install clickhouse-odbc-bridge (must match server version exactly)
RUN apt-get update \
    && apt-get install -y clickhouse-odbc-bridge \
    && apt-get clean
