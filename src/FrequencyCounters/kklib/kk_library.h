/******************************************************************************
** PROJECT: KK Library
** FILE:    kk_library.h
**
** CONTACT: info@kplusk-messtechnik.de
**
**
**                     -- ABSTRACT --
**
** C Header file includes function declarations of exported functions from
** Multi Source KK Library version 19.02.00
** KK Library controls and communicates with K+K measuring cards.
**
**
**                     -- HISTORY --
**
**  2019-09-26  lb  new created
**  2020-10-01  lb  updated KK Library version 18.01.10
**  2021-05-28  lb  updated KK Library version 19.00.02
**  2021-11-18  lb  updated KK Library version 19.01.02
**  2021-12-20  lb  updated KK Library version 19.02.00
**  2022-04-08  lb  syntax error Multi_DebugGetFilename
**  2023-01-04  lb  updated KK Library version 19.03.01
******************************************************************************/

// create multi source object   -----------------------------------------------
int CreateMultiSource(void);

// list available interfaces    -----------------------------------------------
int    Multi_EnumerateDevices(char *Names, unsigned char EnumFlags);
char * Multi_GetEnumerateDevicesErrorMsg(void);
int    Multi_GetHostAndIPs(char *HostName, char *IPaddr, char * ErrorMsg);
// hint requires 80 byte buffer only

// path definitions             -----------------------------------------------
char * Multi_GetOutputPath(int ID);
char * Multi_SetOutputPath(int ID, char *path);

// Debug protocol               -----------------------------------------------
char * Multi_Debug(int ID, bool DbgOn, char *DbgID);
int    Multi_DebugFlags(int ID, bool ReportLog, bool LowLevelLog);
int    Multi_DebugLogLimit(int ID, unsigned char LogType, unsigned int aSize);
char * Multi_DebugGetFilename(int ID);

// Info queries                 -----------------------------------------------
char * Multi_GetDLLVersion(void);
int    Multi_GetBufferAmount(int ID);
int    Multi_GetTransmitBufferAmount(int ID);
unsigned char Multi_GetUserID(int ID);
bool   Multi_IsFileDevice(int ID);
//     since 18.01.10
int    Multi_GetFirmwareVersion(int ID);
bool   Multi_HasFRAM(int ID);
//     since 19.01.02
bool   Multi_IsSerialDevice(int ID);
//     since 19.03.01
int    Multi_GetDeviceStartState(int ID);

// Calibration                  -----------------------------------------------
//     since 18.01.10
int    Multi_SetNSZCalibrationData(int ID, char *Data);

// FHR-Settings                 -----------------------------------------------
//     since 19.01.02
int    Multi_ReadFHRData(int ID);
int    Multi_SetFHRData(int ID, char *Data);

// open and close connection    -----------------------------------------------
int    Multi_OpenConnection(int ID, char *Connection, bool BlockingIO);
void   Multi_CloseConnection(int ID);

// read reports                 -----------------------------------------------
int    Multi_SetDecimalSeparator(int ID, char Separator);
int    Multi_SetNSZ(int ID, int aNSZ);
int    Multi_GetReport(int ID, char *Data);
//     since 19.03.01
int    Multi_SetSend7016(int ID, bool Value);             

// send commands                -----------------------------------------------
unsigned int Multi_GetPendingCmdsCount(int ID);
int    Multi_SetCommandLimit(int ID, unsigned int Limit);
int    Multi_SendCommand(int ID, char *Command, int Len);
//     since 18.01.10
int    Multi_RemoteLogin(int ID, unsigned int Password, char *err);

// local TCP server             -----------------------------------------------
int    Multi_StartTcpServer(int ID, unsigned short *aPort);
int    Multi_StopTcpServer(int ID);
char * Multi_GetTcpServerError(int ID);
void   Multi_TcpReportLog(int ID, char *Data, int logType);

// connection to TCP server at LOG level  -------------------------------------
int    Multi_OpenTcpLog(int ID, char *IpPort, char *Mode);
void   Multi_CloseTcpLog(int ID);
int    Multi_GetTcpLog(int ID, char *Data);
//     since 19.0.2
int    Multi_OpenTcpLogTime(int ID, char *IpPort, char *Mode, char *Format);
//     since 19.2.2
int    Multi_OpenTcpLogType(int ID, char *IpPort, int LogType, char *Format);
int    Multi_TcpAppData(int ID, char *Data);

// send data to TCP server      -----------------------------------------------
//     since 19.2.0
int    Multi_TcpAppData(int ID, char *Data);

// generate test data           -----------------------------------------------
int    Multi_StartSaveBinaryData(int ID, char *DbgID);
int    Multi_StopSaveBinaryData(int ID);
int    Multi_StartSaveReportData(int ID, char *DbgID);
int    Multi_StopSaveReportData(int ID);
