"""Ověření zdrojů, pro které připnutý AigisCode nevytváří sémantický graf."""
from collections import Counter
from pathlib import Path
import re
import shlex
import subprocess

# JavacTask.parse() načte syntaxi bez spuštění programu, procesorů anotací a bez tříd externích knihoven.
JAVA = """import java.io.*;
import java.util.*;
import javax.tools.*;
import com.sun.source.util.JavacTask;
class KontrolaJavy {
    public static void main(String[] args) throws Exception {
        var compiler = ToolProvider.getSystemJavaCompiler();
        var diagnostics = new DiagnosticCollector<JavaFileObject>();
        try (var files = compiler.getStandardFileManager(diagnostics, null, null)) {
            var inputs = files.getJavaFileObjectsFromStrings(Arrays.asList(args));
            var task = (JavacTask) compiler.getTask(null, files, diagnostics, List.of("-proc:none"), null, inputs);
            task.parse();
            for (var d : diagnostics.getDiagnostics()) {
                if (d.getKind() == Diagnostic.Kind.ERROR) {
                    System.err.println(d.getSource().getName() + ":" + d.getLineNumber() + ": " + d.getMessage(null));
                    System.exit(1);
                }
            }
        }
    }
}
"""

def sql(text):
    from pglast import parse_sql
    statements = []
    conditions = []
    for line in text.splitlines():
        if line.lstrip().startswith("\\"):
            parts = shlex.split(line.lstrip()[1:])
            name, args = parts[0], parts[1:]
            if name == "if" and args:
                conditions.append(False)
            elif name == "else" and not args and conditions and not conditions[-1]:
                conditions[-1] = True
            elif name == "endif" and not args and conditions:
                conditions.pop()
            elif name in ("set", "connect", "echo", "quit") and (args or name == "quit"):
                pass
            else:
                raise ValueError("Nepodporovaný nebo neplatný příkaz psql: " + name)
        else:
            # psql odesílá příkaz končící gset stejně jako při středníku.
            line = re.sub(r"\s+\\gset\s*$", ";", line)
            line = re.sub(r"(?<!:):'([A-Za-z_][A-Za-z_0-9]*)'", "'test'", line)
            statements.append(line)
    if conditions:
        raise ValueError("Neuzavřená podmínka psql")
    parse_sql("\n".join(statements))

def over(root, unsupported, tools_dir):
    counts = Counter()
    java = []
    astro = []
    for item in unsupported:
        relative = Path(item["file_path"])
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts or path.resolve() != path or not path.is_file():
            raise ValueError("Neplatná cesta z inventáře AigisCode")
        lang = item["extension"]
        if relative.suffix.lower() != "." + lang:
            raise ValueError("Nesouhlasí jazyk zdroje")
        counts[lang] += 1
        if lang in ("sh", "bash"):
            subprocess.run(["/bin/bash","-n",path],check=True,timeout=30)
        elif lang == "go":
            subprocess.run(["gofmt",path],stdout=subprocess.DEVNULL,check=True,timeout=30)
        elif lang == "astro":
            astro.append(path)
        elif lang == "java":
            java.append(path)
        elif lang == "sql":
            try:
                sql(path.read_text())
            except Exception as error:
                raise ValueError("Kontrola PostgreSQL selhala: " + str(relative)) from error
        else:
            raise ValueError("Chybí kontrola jazyka: " + lang)
    if astro:
        subprocess.run(["/opt/polarita-astro-ci/node", "/opt/polarita-astro-ci/astro.cjs", *astro],
                       check=True, timeout=120)
    if java:
        program = tools_dir / "KontrolaJavy.java"
        program.write_text(JAVA)
        subprocess.run(["java","-Xmx64m",program,*java],check=True,timeout=90)
    print("Jazykové kontroly všech zdrojů mimo podporu AigisCode:", dict(sorted(counts.items())), flush=True)
