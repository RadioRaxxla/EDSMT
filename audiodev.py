"""Which audio device EDSMT's voice and sounds play on (1.10042, G2).

By default everything plays on the system's default output device, as it
always has. A commander can pick another - a headset, say, while the game
is on the speakers - and this module is the plain part of that: reading
the list of devices Windows gives, the choices a box offers, falling back
to the default when the device chosen is gone, and the PowerShell scripts.

What can be pointed. System.Speech's SpeechSynthesizer and the
System.Media.SoundPlayer the plain speech script uses have no way to name
an output device: they play on the default one. What does have one is the
Windows Runtime's MediaPlayer, whose AudioDevice property takes a
DeviceInformation found with the audio render selector of MediaDevice. So
with a device chosen the speech process is the second script below: a line
of text is spoken to a temporary wave file by System.Speech and a recording
is opened as it is, and both are played by a MediaPlayer on that device.
With none chosen the plain script is used, unchanged. The proximity sonar's
tones are made by winsound.Beep, which has no device either, and stay on the
default device.

The list and the pointing sit behind objects a check can replace
(DeviceList, a backend with devices()); nothing here needs Windows to be
tested. Anywhere but Windows there is nothing to choose and nothing is
spoken.
"""

import os
import threading

DEFAULT_NAME = "System default"
GONE_NAME = "Chosen device (not connected)"

# What Windows says about the output devices, one a line: id, a tab, name.
LIST_SCRIPT = "\n".join((
    "$ErrorActionPreference = 'Stop'",
    "$ProgressPreference = 'SilentlyContinue'",
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
    "Add-Type -AssemblyName System.Runtime.WindowsRuntime",
    "[void][Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, "
    "ContentType=WindowsRuntime]",
    "[void][Windows.Media.Devices.MediaDevice, Windows.Media, ContentType=WindowsRuntime]",
    "$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
    "$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
    "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1",
    "$op = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync("
    "[Windows.Media.Devices.MediaDevice]::GetAudioRenderSelector())",
    "$task = $asTask.MakeGenericMethod("
    "[Windows.Devices.Enumeration.DeviceInformationCollection]).Invoke($null, @($op))",
    "$task.Wait(-1) | Out-Null",
    "foreach ($d in $task.Result) { [Console]::Out.WriteLine($d.Id + \"`t\" + $d.Name) }",
))

# The speech process for a chosen device. The same commands as the plain
# script - R rate, S text, W file - and D, the device to play on (- for the
# default). A device that cannot be used is reported as "E D <reason>" and
# the default is played on instead.
DEVICE_SPEECH_SCRIPT = "\n".join((
    "$ErrorActionPreference = 'Stop'",
    "$ProgressPreference = 'SilentlyContinue'",
    "function Why($e) {",
    "  if ($e.Exception.InnerException) { $e.Exception.InnerException.Message }",
    "  else { $e.Exception.Message }",
    "}",
    "$voice = $null",
    "try {",
    "  Add-Type -AssemblyName System.Speech",
    "  $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer",
    "} catch { $voice = $null; [Console]::Error.WriteLine('E ! ' + (Why $_)) }",
    "$device = $null",
    "$winrt = $false",
    "$asTask = $null",
    "try {",
    "  Add-Type -AssemblyName System.Runtime.WindowsRuntime",
    "  [void][Windows.Media.Playback.MediaPlayer, Windows.Media, ContentType=WindowsRuntime]",
    "  [void][Windows.Media.Core.MediaSource, Windows.Media, ContentType=WindowsRuntime]",
    "  [void][Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]",
    "  [void][Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, "
    "ContentType=WindowsRuntime]",
    "  $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
    "$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
    "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1",
    "  $winrt = $true",
    "} catch { [Console]::Error.WriteLine('E D ' + (Why $_)) }",
    "function Await($op, $type) {",
    "  $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))",
    "  $task.Wait(-1) | Out-Null",
    "  $task.Result",
    "}",
    # Play a wave file on the chosen device, to its end; on the default
    # device with the sound player when there is none or it cannot be used.
    "function PlayFile($path) {",
    "  if ($device -eq $null -or -not $winrt) {",
    "    (New-Object System.Media.SoundPlayer $path).PlaySync()",
    "    return",
    "  }",
    "  $player = New-Object Windows.Media.Playback.MediaPlayer",
    "  try {",
    "    $player.AudioDevice = $device",
    "    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) "
    "([Windows.Storage.StorageFile])",
    "    $player.Source = [Windows.Media.Core.MediaSource]::CreateFromStorageFile($file)",
    "    $player.Play()",
    "    $until = [DateTime]::UtcNow.AddSeconds(60)",
    "    Start-Sleep -Milliseconds 200",
    "    while ([DateTime]::UtcNow -lt $until) {",
    "      $state = [string]$player.PlaybackSession.PlaybackState",
    "      if ($state -eq 'Paused' -or $state -eq 'None') { break }",
    "      Start-Sleep -Milliseconds 50",
    "    }",
    "  } finally { $player.Dispose() }",
    "}",
    "$lines = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), "
    "[System.Text.Encoding]::UTF8)",
    "while ($true) {",
    "  $line = $lines.ReadLine()",
    "  if ($line -eq $null) { break }",
    "  if ($line.Length -lt 3) { continue }",
    "  $what = $line.Substring(0, 1)",
    "  $rest = $line.Substring(2)",
    "  try {",
    "    if ($what -eq 'R') { if ($voice -ne $null) { $voice.Rate = [int]$rest } }",
    "    elseif ($what -eq 'D') {",
    "      $device = $null",
    "      if ($rest -ne '-' -and $winrt) {",
    "        $device = Await ([Windows.Devices.Enumeration.DeviceInformation]::CreateFromIdAsync($rest)) "
    "([Windows.Devices.Enumeration.DeviceInformation])",
    "      }",
    "    }",
    "    elseif ($what -eq 'S') {",
    "      if ($voice -eq $null) { throw 'Windows speech is not available on this PC' }",
    "      if ($device -eq $null -or -not $winrt) { $voice.Speak($rest) }",
    "      else {",
    "        $tmp = Join-Path ([System.IO.Path]::GetTempPath()) "
    "('edsmt-say-' + [guid]::NewGuid().ToString('N') + '.wav')",
    "        try {",
    "          $voice.SetOutputToWaveFile($tmp)",
    "          $voice.Speak($rest)",
    "          $voice.SetOutputToDefaultAudioDevice()",
    "          PlayFile $tmp",
    "        } finally {",
    "          try { $voice.SetOutputToDefaultAudioDevice() } catch { }",
    "          Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue",
    "        }",
    "      }",
    "    }",
    "    elseif ($what -eq 'W') { PlayFile $rest }",
    "  } catch {",
    "    if ($what -eq 'D') { $device = $null; [Console]::Error.WriteLine('E D ' + (Why $_)) }",
    "    else { [Console]::Error.WriteLine('E ' + $what + ' ' + (Why $_)) }",
    "  }",
    "}",
))


def parse_devices(raw):
    """[(id, name)] from the list script's output - bytes or text - one a
    line, id then a tab then the name. Lines that are not that, and a device
    seen twice, are left out; anything unreadable is an empty list."""
    if raw is None:
        return []
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return []
    seen, out = set(), []
    for line in str(raw).splitlines():
        ident, tab, name = line.strip("\r\n").partition("\t")
        ident, name = ident.strip(), name.strip()
        if not tab or not ident or not name or ident in seen:
            continue
        seen.add(ident)
        out.append((ident, name))
    return out


def device_choices(devices, keep=""):
    """[(name, id)] for a box: the system default first, each device by
    name (two with one name told apart), and - so Save does not lose it - the
    device chosen earlier when it is not among them."""
    names = {}
    for _ident, name in devices or ():
        names[name] = names.get(name, 0) + 1
    out, count = [(DEFAULT_NAME, "")], {}
    for ident, name in devices or ():
        count[name] = count.get(name, 0) + 1
        out.append((name if names[name] == 1 else "%s (%d)" % (name, count[name]), ident))
    if keep and isinstance(keep, str) and keep not in [i for _n, i in out]:
        out.append((GONE_NAME, keep))
    return out


def choose(saved, devices):
    """(the device id to play on, a note): the one saved when it is there,
    else "" - the default - with a note saying so when something was saved.
    `devices` None means the list has not been read yet: the choice stands."""
    if not isinstance(saved, str) or not saved:
        return "", ""
    if devices is None or saved in [ident for ident, _name in devices]:
        return saved, ""
    return "", ("The audio device you chose is not connected, so the default "
                "device is used until it is.")


class NoDevices:
    """Anywhere but Windows: there is nothing to choose from."""
    available = False
    problem = ""

    def devices(self):
        return []


class WindowsDevices:
    """The output devices Windows lists, through `run(script)` - which runs a
    PowerShell script and gives back what it wrote, as bytes. A check hands
    it a stand-in."""
    available = True

    def __init__(self, run):
        self._run = run
        self.problem = ""

    def devices(self):
        self.problem = ""
        try:
            return parse_devices(self._run(LIST_SCRIPT))
        except (OSError, ValueError) as exc:
            self.problem = "The list of audio devices could not be read: %s" % exc
            return []


def windows_backend(powershell_command):
    """The real list of devices on Windows, NoDevices elsewhere.
    `powershell_command(script)` is voice.powershell_command."""
    if os.name != "nt":
        return NoDevices()

    def run(script):
        import subprocess
        done = subprocess.run(powershell_command(script), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              creationflags=0x08000000, timeout=20)
        return done.stdout
    return WindowsDevices(run)


class DeviceList:
    """The devices, read on a thread of its own so no window waits for
    PowerShell. items() is None until the first reading is done."""

    def __init__(self, backend):
        self.backend = backend
        self._items = None
        self._lock = threading.Lock()
        self._busy = False
        self.problem = ""

    @property
    def available(self):
        return bool(getattr(self.backend, "available", False))

    @property
    def ready(self):
        return self._items is not None and not self._busy

    def items(self):
        return None if self._items is None else list(self._items)

    def reload(self):
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._read, name="EDSMT audio devices", daemon=True).start()

    def _read(self):
        try:
            found = list(self.backend.devices())
            self.problem = str(getattr(self.backend, "problem", "") or "")
        except Exception as exc:
            found, self.problem = [], "The list of audio devices could not be read: %s" % exc
        self._items = found
        self._busy = False
