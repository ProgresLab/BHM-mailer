"""Bounded read-only Windows listener diagnostics, without process arguments."""
import ctypes
import json
import os
import struct
import subprocess


def process_cwd(pid):
    """Read the Windows PEB current directory; permissions/bitness fail closed."""
    if os.name!='nt':
        return 'unavailable'
    from ctypes import wintypes as w
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.ReadProcessMemory.argtypes=[w.HANDLE,w.LPCVOID,w.LPVOID,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    ntdll=ctypes.WinDLL('ntdll')
    ntdll.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,w.LPVOID,w.ULONG,ctypes.POINTER(w.ULONG)]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:
        return 'unavailable (access denied)'
    try:
        width=ctypes.sizeof(ctypes.c_void_p)
        wow=w.BOOL()
        kernel.IsWow64Process.argtypes=[w.HANDLE,ctypes.POINTER(w.BOOL)]
        if not kernel.IsWow64Process(handle,ctypes.byref(wow)) or wow.value:
            return 'unavailable (process bitness)'
        def read(address,size):
            buf=ctypes.create_string_buffer(size);count=ctypes.c_size_t()
            if not kernel.ReadProcessMemory(handle,address,buf,size,ctypes.byref(count)) or count.value!=size:
                raise OSError('Cannot read process directory')
            return buf.raw
        basic=ctypes.create_string_buffer(width*6);returned=w.ULONG()
        if ntdll.NtQueryInformationProcess(handle,0,basic,len(basic),ctypes.byref(returned))!=0:
            raise OSError('Cannot query process')
        pointer=lambda b:int.from_bytes(b,'little')
        peb=pointer(basic.raw[width:width*2])
        params=pointer(read(peb+(0x20 if width==8 else 0x10),width))
        directory=read(params+(0x38 if width==8 else 0x24),width*2)
        size=struct.unpack_from('<H',directory)[0]
        if size>32766 or size%2:
            raise OSError('Invalid directory length')
        return read(pointer(directory[width:width*2]),size).decode('utf-16-le')
    except (OSError,ValueError):
        return 'unavailable (access/architecture)'
    finally:
        kernel.CloseHandle(handle)


def port_owner(port):
    result=dict(port=port,pid=None,cwd='unavailable',owner='unavailable')
    if os.name!='nt':
        return result
    script=("$pids=@(Get-NetTCPConnection -State Listen -LocalPort "+str(int(port))+
        " -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique); "
        "$rows=@(foreach($processId in $pids){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$processId);"
        "$o=Invoke-CimMethod -InputObject $p -MethodName GetOwner;"
        "[pscustomobject]@{pid=$processId;owner=($o.Domain+'\\'+$o.User);executable=$p.ExecutablePath}});"
        "ConvertTo-Json -Compress -InputObject $rows")
    try:
        output=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            timeout=8,text=True,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        owners=json.loads(output)
        for entry in owners:
            entry['cwd']=process_cwd(entry['pid'])
        return dict(port=port,processes=owners)
    except (OSError,ValueError,subprocess.SubprocessError):
        return result
