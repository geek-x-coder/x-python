import jaydebeapi as jdbc
from xLogger.xLogWriter import LogWriter, LogLevel

import pandas as pd
import sys

from sqlalchemy import create_engine

class DBHandler : 
    def __init__(self, isDisplayLog = False) :
        self.logger = LogWriter(isDisplayLog)
        self.dbInfo = ""
        self.host = ""
        self.port = ""
        self.database = ""
        self.user = ""
        self.password = ""
        
    def getMethodName (self) : 
        return f"{self.__class__.__name__}.{sys._getframe(1).f_code.co_name}"
    
    def connect(self, dbms, host, port, database, user, password, jdbcDriver):
        try: 
            self.host = host
            self.port = port
            self.database = database
            self.user = user
            self.password = password
            
            self.dbInfo = f"host:{host}, port:{port}, database:{database}, user:{user}"
            
            if dbms.upper() == "MARIA" :
                driverClass = "org.mariadb.jdbc.Driver"
                url = f"jdbc:mariadb://{host}:{port}/{database}"
                self.conn = jdbc.connect(driverClass, url,
                                         driver_args={"user":user, "password":password},
                                         jars=jdbcDriver)
            elif dbms.upper() == "ORACLE":
                driverClass = "oracle.jdbc.OracleDriver"
                url = f"jdbc:oracle:thin:@{host}:{port}/{database}"
                self.conn = jdbc.connect(driverClass, url,
                                         driver_args={"user":user, "password":password},
                                         jars=jdbcDriver)
            else :
                self.logger.printLog(f"Failed to connect Database >> DBMS not supported [{dbms.upper()}]", LogLevel.warning)
                return False
            
            self.cursor = self.conn.cursor()
            
            self.logger.printLog(f"Connected o Database >> {self.dbInfo}", LogLevel.info)
            return True
            
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{e}", LogLevel.exception)
            return False
        
    def commit(self) :
        try:
            self.conn.commit()
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{e}", LogLevel.exception)
            
    def rollback(self) :
        try:
            self.conn.rollback()
            self.logger.printLog(f"DB Transaction Rollback >> {self.dbInfo}", LogLevel.warning)
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{e}", LogLevel.exception)
            
    def close(self) :
        try :
            self.cursor.close()
            self.conn.close()
            self.logger.printLog(f"Disconnected from Database >> {self.dbInfo}", LogLevel.info)
        except Exception as e :
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{e}", LogLevel.exception)
            
    def execute(self, sql) :
        try :
            self.cursor.execute(sql)
            self.logger.printLog(f"SQL execution succeeded >> rowcount:{self.cursor.rowcount} \n{sql}", LogLevel.info)
            return True
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{sql} \n{e}", LogLevel.exception)
            
    def executeReturnCurosr(self, sql):
        try:
            self.cursor.execute(sql)
            self.logger.printLog(f"SQL execution succeeded >> rowcount:{self.cursor.rowcount} \n{sql}", LogLevel.info)
            return self.cursor
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{sql} \n{e}", LogLevel.exception)
    
    def executeFetchAll(self, sql) :
        try:
            self.cursor.execute(sql)
            self.logger.printLog(f"SQL execution succeeded >> rowcount:{self.cursor.rowcount} \n{sql}", LogLevel.info)
            return self.cursor.fetchall()
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{sql} \n{e}", LogLevel.exception)
    
    def read_sql_query(self, sql) :
        try:
            df = pd.read_sql_query(sql=sql, con=self.conn)
            self.logger.printLog(f"SQL execution succeeded >> rowcount:{df.count()}\n{sql}", LogLevel.info)
            return df
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{sql} \n{e}", LogLevel.exception)
            
    def to_sql(self, schema, tableName, columnHeader, data, columnPropertyList) :
        try : 
            with create_engine(f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?utf-8").begin() as conn :
                df = pd.DataFrame(data, columns=columnHeader)
                
                for columnProperty in columnPropertyList:
                    if columnProperty.isNullable is False and columnProperty.defaultValue.upper() not in ["NULL", "NONE", "''"]:
                        if df[columnProperty.name].isnull().sum() > 0 :
                            df[columnProperty.name].fillna(columnProperty.defaultValue.replace("'", ""), inplace=True)
                            
                df.to_sql(schema=schema, name=tableName, con=conn, if_exists='append', index=False)
            
            if conn.closed is not True :
                conn.close()
                
            return True
        
        except Exception as e:
            self.logger.printLog(f"An exception occurred >> {self.getMethodName()} \n{e}", LogLevel.exception)
            return False