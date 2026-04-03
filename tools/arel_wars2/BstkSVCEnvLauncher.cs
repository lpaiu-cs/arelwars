using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

internal static class Program
{
    private static int Main(string[] args)
    {
        const string BstkSvcPath = @"C:\vs\other\arelwars\$root\PF\BstkSVC.exe";
        const string Home = @"C:\Users\lpaiu";
        const string VBoxUserHome = @"C:\ProgramData\BlueStacks_nxt\Engine\Manager";
        const string VBoxAppHome = @"C:\ProgramData\BlueStacks_nxt";
        const string TempDir = @"C:\bstk";
        const string LogPath = @"C:\bstk\bstk-wrapper.log";

        Directory.CreateDirectory(TempDir);
        Directory.CreateDirectory(Path.GetDirectoryName(LogPath) ?? TempDir);

        var quotedArgs = string.Join(" ", args.Select(QuoteArg));
        var log = new StringBuilder();
        log.Append('[').Append(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff")).Append("] ");
        log.Append("args=").Append(quotedArgs).AppendLine();
        log.Append("  HOME=").Append(Home).AppendLine();
        log.Append("  VBOX_USER_HOME=").Append(VBoxUserHome).AppendLine();
        log.Append("  VBOX_APP_HOME=").Append(VBoxAppHome).AppendLine();
        log.Append("  TEMP=").Append(TempDir).AppendLine();
        log.Append("  TMP=").Append(TempDir).AppendLine();
        File.AppendAllText(LogPath, log.ToString(), Encoding.UTF8);

        var psi = new ProcessStartInfo
        {
            FileName = BstkSvcPath,
            Arguments = quotedArgs,
            WorkingDirectory = Path.GetDirectoryName(BstkSvcPath) ?? Environment.CurrentDirectory,
            UseShellExecute = false,
        };
        psi.Environment["HOME"] = Home;
        psi.Environment["VBOX_USER_HOME"] = VBoxUserHome;
        psi.Environment["VBOX_APP_HOME"] = VBoxAppHome;
        psi.Environment["TEMP"] = TempDir;
        psi.Environment["TMP"] = TempDir;

        var process = Process.Start(psi);
        if (process == null)
        {
            File.AppendAllText(LogPath, "  ERROR=Process.Start returned null" + Environment.NewLine, Encoding.UTF8);
            return 1;
        }

        try
        {
            File.AppendAllText(LogPath, "  childPid=" + process.Id + Environment.NewLine, Encoding.UTF8);
            process.WaitForExit();
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
