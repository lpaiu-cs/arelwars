using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

internal static class Program
{
    private static int Main(string[] args)
    {
        const string BstkSvcPath = @"B:\BstkSVC.exe";
        const string VBoxUserHome = @"R:\Engine\Manager";
        const string VBoxAppHome = @"R:\";
        const string TempDir = @"R:\Logs";
        const string LogPath = @"R:\Logs\bstk-wrapper.log";
        const string Home = VBoxUserHome;
        const string UserProfile = VBoxUserHome;
        const string AppData = VBoxUserHome;
        const string LocalAppData = VBoxUserHome;
        const string HomeDrive = @"R:";
        const string HomePath = @"\Engine\Manager";
        const string ReleaseLog = @"R:\Logs\BstkServer.log";

        Directory.CreateDirectory(TempDir);
        Directory.CreateDirectory(Path.GetDirectoryName(LogPath) ?? TempDir);

        var forwardedArgs = args.ToList();
        if (!forwardedArgs.Any(arg => string.Equals(arg, "--logfile", StringComparison.OrdinalIgnoreCase)))
        {
            forwardedArgs.Add("--logfile");
            forwardedArgs.Add(ReleaseLog);
        }
        var quotedArgs = string.Join(" ", forwardedArgs.Select(QuoteArg));
        var log = new StringBuilder();
        log.Append('[').Append(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff")).Append("] ");
        log.Append("wrapper=v5").AppendLine();
        log.Append("  exe=").Append(System.Reflection.Assembly.GetExecutingAssembly().Location).AppendLine();
        log.Append("args=").Append(quotedArgs).AppendLine();
        log.Append("  HOME=").Append(Home).AppendLine();
        log.Append("  USERPROFILE=").Append(UserProfile).AppendLine();
        log.Append("  APPDATA=").Append(AppData).AppendLine();
        log.Append("  LOCALAPPDATA=").Append(LocalAppData).AppendLine();
        log.Append("  HOMEDRIVE=").Append(HomeDrive).AppendLine();
        log.Append("  HOMEPATH=").Append(HomePath).AppendLine();
        log.Append("  VBOX_USER_HOME=").Append(VBoxUserHome).AppendLine();
        log.Append("  VBOX_APP_HOME=").Append(VBoxAppHome).AppendLine();
        log.Append("  TEMP=").Append(TempDir).AppendLine();
        log.Append("  TMP=").Append(TempDir).AppendLine();
        log.Append("  VBOXSVC_RELEASE_LOG=").Append(ReleaseLog).AppendLine();
        File.AppendAllText(LogPath, log.ToString(), Encoding.UTF8);

        var psi = new ProcessStartInfo
        {
            FileName = BstkSvcPath,
            Arguments = quotedArgs,
            WorkingDirectory = Path.GetDirectoryName(BstkSvcPath) ?? Environment.CurrentDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        psi.Environment["HOME"] = Home;
        psi.Environment["USERPROFILE"] = UserProfile;
        psi.Environment["APPDATA"] = AppData;
        psi.Environment["LOCALAPPDATA"] = LocalAppData;
        psi.Environment["HOMEDRIVE"] = HomeDrive;
        psi.Environment["HOMEPATH"] = HomePath;
        psi.Environment["VBOX_USER_HOME"] = VBoxUserHome;
        psi.Environment["VBOX_APP_HOME"] = VBoxAppHome;
        psi.Environment["TEMP"] = TempDir;
        psi.Environment["TMP"] = TempDir;
        psi.Environment["VBOXSVC_RELEASE_LOG"] = ReleaseLog;

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
