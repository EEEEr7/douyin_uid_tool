# Shared Windows shell integration for desktop shortcuts.
$script:AppUserModelId = "XTeink.DouyinUIDTool.1"

function Set-ShortcutAppUserModelId {
    param(
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$AppUserModelId
    )

    if (-not (Test-Path -LiteralPath $ShortcutPath)) {
        Write-Error "Shortcut not found: $ShortcutPath"
    }

    $type = @'
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential, Pack = 4)]
public struct PropertyKey { public Guid fmtid; public uint pid; }

[StructLayout(LayoutKind.Explicit, Size = 16)]
public struct PropVariant {
    [FieldOffset(0)] public ushort vt;
    [FieldOffset(8)] public IntPtr ptr;
}

[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CBA1DBDCF279"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
    void GetCount(out uint cProps);
    void GetAt(uint iProp, out PropertyKey pkey);
    void GetValue(ref PropertyKey key, out PropVariant pv);
    void SetValue(ref PropertyKey key, ref PropVariant pv);
    void Commit();
}

public static class ShortcutAppIdHelper {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHGetPropertyStoreFromParsingName(
        string pszPath, IntPtr bc, uint flags, ref Guid riid, out IntPtr ppv);

    static Guid IID_IPropertyStore = new Guid("886D8EEB-8CF2-4446-8D02-CBA1DBDCF279");
    static PropertyKey PKEY_AppUserModel_ID = new PropertyKey {
        fmtid = new Guid("9F4C2855-9F79-4F39-8B8D-8E15011BE99B"), pid = 5
    };

    public static void Set(string path, string appId) {
        IntPtr ppv;
        SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 0x12, ref IID_IPropertyStore, out ppv);
        if (ppv == IntPtr.Zero) {
            throw new InvalidOperationException("SHGetPropertyStoreFromParsingName returned null.");
        }
        try {
            var store = (IPropertyStore)Marshal.GetObjectForIUnknown(ppv);
            var pv = new PropVariant { vt = 31, ptr = Marshal.StringToCoTaskMemUni(appId) };
            store.SetValue(ref PKEY_AppUserModel_ID, ref pv);
            store.Commit();
            Marshal.FreeCoTaskMem(pv.ptr);
        } finally {
            Marshal.Release(ppv);
        }
    }
}
'@

    if (-not ("ShortcutAppIdHelper" -as [type])) {
        Add-Type -TypeDefinition $type -Language CSharp -ErrorAction Stop
    }

    try {
        [ShortcutAppIdHelper]::Set($ShortcutPath, $AppUserModelId)
    } catch {
        Write-Warning "Could not set AppUserModelID on shortcut: $($_.Exception.Message)"
    }
}
