using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

internal static class Program
{
    private static int Main(string[] args)
    {
        const string OracleVBoxDir = @"C:\Program Files\Oracle\VirtualBox";
        const string OracleVBoxHeadless = @"C:\Program Files\Oracle\VirtualBox\VBoxHeadless.exe";
        const string DataDir = @"C:\ProgramData\BlueStacks_nxt";
        const string ManagerDir = @"C:\ProgramData\BlueStacks_nxt\Manager";
        const string LogPath = @"C:\ProgramData\BlueStacks_nxt\Logs\VBoxHeadless-proxy.log";

        Directory.CreateDirectory(Path.GetDirectoryName(LogPath) ?? DataDir);
        var quotedArgs = string.Join(" ", args.Select(QuoteArg));
        var log = new StringBuilder();
        log.Append('[').Append(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff")).Append("] ");
        log.Append("proxy=v1").AppendLine();
        log.Append("  exe=").Append(System.Reflection.Assembly.GetExecutingAssembly().Location).AppendLine();
        log.Append("  target=").Append(OracleVBoxHeadless).AppendLine();
        log.Append("  args=").Append(quotedArgs).AppendLine();
        File.AppendAllText(LogPath, log.ToString(), Encoding.UTF8);

        var psi = new ProcessStartInfo
        {
            FileName = OracleVBoxHeadless,
            Arguments = quotedArgs,
            WorkingDirectory = OracleVBoxDir,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        var machinePath = psi.Environment.ContainsKey("PATH")
            ? psi.Environment["PATH"]
            : Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        psi.Environment["PATH"] = OracleVBoxDir + ";" + machinePath;
        psi.Environment["HOME"] = ManagerDir;
        psi.Environment["USERPROFILE"] = ManagerDir;
        psi.Environment["APPDATA"] = ManagerDir;
        psi.Environment["LOCALAPPDATA"] = ManagerDir;
        psi.Environment["VBOX_USER_HOME"] = ManagerDir;
        psi.Environment["VBOX_APP_HOME"] = DataDir;
        psi.Environment["TEMP"] = Path.Combine(DataDir, "Logs");
        psi.Environment["TMP"] = Path.Combine(DataDir, "Logs");

        var process = Process.Start(psi);
        if (process == null)
        {
            File.AppendAllText(LogPath, "  ERROR=Process.Start returned null" + Environment.NewLine, Encoding.UTF8);
            return 1;
        }

        try
        {
            File.AppendAllText(LogPath, "  childPid=" + process.Id + Environment.NewLine, Encoding.UTF8);
            string stdOut = process.StandardOutput.ReadToEnd();
            string stdErr = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (!string.IsNullOrWhiteSpace(stdOut))
            {
                File.AppendAllText(LogPath, "  stdout=" + stdOut + Environment.NewLine, Encoding.UTF8);
            }
            if (!string.IsNullOrWhiteSpace(stdErr))
            {
                File.AppendAllText(LogPath, "  stderr=" + stdErr + Environment.NewLine, Encoding.UTF8);
            }
            File.AppendAllText(LogPath, "  childExit=" + process.ExitCode + Environment.NewLine, Encoding.UTF8);
            return process.ExitCode;
        }
        finally
        {
            process.Dispose();
        }
    }

    private static string QuoteArg(string arg)
    {
        if (string.IsNullOrEmpty(arg))
        {
            return "\"\"";
        }

        if (!arg.Any(ch => char.IsWhiteSpace(ch) || ch == '"'))
        {
            return arg;
        }

        return "\"" + arg.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }
}
