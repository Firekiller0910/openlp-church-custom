using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class OpenLPCustomLauncher
{
    [STAThread]
    private static void Main()
    {
        string directory = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(directory, "runtime", "pythonw.exe");
        string launcher = Path.Combine(directory, "launch.py");
        try
        {
            if (!File.Exists(python) || !File.Exists(launcher))
                throw new FileNotFoundException("Extract the entire ZIP before opening OpenLP Custom. Keep its runtime and source folders together.");
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "\"" + launcher + "\"";
            info.WorkingDirectory = directory;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process.Start(info);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "OpenLP Custom", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
