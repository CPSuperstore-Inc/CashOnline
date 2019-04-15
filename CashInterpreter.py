"""
Usage:
    interpret_command(COMMAND)
    use interpret_command("help") to return a list of commands

Returns:
    list. Each item in the list is a new line in the command's output

Customization:
    modify any of the items in the "config" dictionary to set properties

Variables:
    the "variables" dictionary contains all of the variables in memory. 
    you can add values in it, and they will be there on startup 
"""

# region Imports
import os
import subprocess
import shutil
import time
import sys
import zipfile
import datetime
import platform
import getpass
import requests
import traceback
import sqlite3
# import mysql.connector  # pip install mysql-connector-python

# endregion


# region System Configuration
config = {
    "file": "config.json"
}

if "file" in config:
    config = eval(''.join(open(config["file"], 'r').readlines()))

# the initial variables
variables = {
    "cash": "awesome"
}

SQL = False
selected_database = None
# endregion


# region Main Scripts

# save the base directory
directory_path = config["directory_root"]

# determine the current working directory by combining the base path and the start location
cwd = directory_path + config["start_location"]

# this list contains all command history
command_history = []

# this is a string for temporary storage
temporary_storage = ""

# this is the list that contains the output, and is returned
return_value = []


def interpret_command(command):
    # this function takes a string, that it will interpret as the command

    # copy the return value, and clear it
    global return_value
    return_value = []

    # add the command to the command history
    command_history.append(command)

    output_mode = 0  # 0 = console, 1 = overwrite file, 2 = append file
    output_name = None  # if 1, or 2, this will contain the filename

    if SQL is True:
        execute_sql(command, selected_database)
        return return_value

    # check if overwrite mode is enabled
    if " > " in command:

        # set the output mode, and filename
        output_mode = 1
        output_name = cwd + "/" + command[command.index(" > ") + 3:]

        # extract the raw command
        command = command[:command.index(" >")]

    # check if append mode is enabled
    elif " >> " in command:

        # set the output mode, and filename
        output_mode = 2
        output_name = cwd + "/" + command[command.index(" >> ") + 4:]

        # extract the raw command
        command = command[:command.index(" >")]

    # check if the command is the path to a file
    if os.path.isfile(cwd + "/" + command):
        # if it is, execute as a file
        execute_file(os.getcwd() + "/" + cwd + "/" + command)

    # check if the command is a variable
    elif command in variables:
        # return the variable's value
        return_value.append(str(variables[command]))

    # if none of the above are true, compile the command
    else:
        # format the command into function notation
        if command.split(" ")[0] in config["disabled_commands"]:
            return_value.append("Disabled Command. Use 'help' For A List Of Commands")
        else:
            original = command
            command = command_to_function(command)
            try:
                # execute the function
                exec(command)
            except (NameError, SyntaxError, TypeError) as e:
                # if a NameError, SyntaxError, or TypeError is thrown, alert the user that the command is unknown

                ignore_messages = [
                    "name '{}' is not defined".format(original)
                ]
                ignore_errors = [
                    SyntaxError,
                    TypeError
                ]

                if str(e) in ignore_messages or type(e) in ignore_errors:
                    return_value.append("Unknown Command. Use 'help' For A List Of Commands")
                else:
                    dump(locals())

            except IndexError:
                # it an IndexError is thrown, alert the user that there are missing arguements,
                # and refers them to the command's help text
                return_value.append(
                    "Missing Argument. Use {} -h For More Information".format(command[:command.index("(")]))

            except:
                # if there are any other exceptions, dump all of the data to a dump file
                dump(locals())

    # if the output mode is overwrite mode
    if output_mode == 1:

        # overwrite the file with the output
        tmp = open(output_name, 'w')
        tmp.write("\n".join(return_value) + "\n")
        tmp.close()

    # if the output mode is append
    elif output_mode == 2:

        # append to the file with the output
        tmp = open(output_name, 'a')
        tmp.write("\n".join(return_value) + "\n")
        tmp.close()

    # return the list of output
    return return_value


# endregion


# region Classes
class SQLConnection:
    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password
        self.c = None
        self.conn = None

        self.connect()
        # try:
        #     self.connect()
        # except mysql.connector.InterfaceError:
        #     return_value.append("Failed To Connect To Database At '{}'".format(self.url))

    def connect(self):
        # if self.username is not None and self.password is not None:
        #     self.conn = mysql.connector.connect(
        #         host=self.url,
        #         user=self.username,
        #         password=self.password,
        #         database="songs"
        #     )
        # else:
        self.conn = sqlite3.connect(self.url, check_same_thread=False)

        self.c = self.conn.cursor()

    def execute_update(self, query):
        self.c.execute(query)
        self.conn.commit()
        return self.c.fetchall()

    @property
    def description(self):
        return self.c.description


# endregion


# region Supporting Functions
def get_command_args(command):
    base = []
    args = []

    for i in command:
        if i.startswith("-"):
            args.append(i.replace("-", ""))
        else:
            base.append(i)

    return base, args


def command_to_function(command):
    command = command.split(" ")
    statement = command[0] + "('"
    for i in command[1:]:
        if i.replace("-", "") == "h" or i.replace("-", "") == "help":
            return "return_value.append(get_docstring('{}'))".format(command[0])
        statement += i + "', '"

    if len(command[1:]) > 0:
        statement = statement[:-3]
    else:
        statement = statement[:-1]
    statement += ")"

    return statement


def get_cwd():
    return cwd


def get_docstring(module_name):
    code = "global temporary_storage\ntemporary_storage = {}.__doc__".format(module_name)
    exec(code)
    if temporary_storage is None:
        return "No Help Available On This Command"
    return temporary_storage


def dump(variables, show_output=True):
    # variables MUST BE locals()

    # cast the value passed in to a dict.
    variables = dict(variables)

    # generate a filename as file_name
    path = config["directory_root"] + config["error_report_directory"]
    if not os.path.isdir(path):
        os.makedirs(path)
    file_name = path + "/" + datetime.datetime.now().strftime(config['dump_file_format']).format(
        fname=config["error_report_filename"])

    # create a new dump file. The name is a combonation of the time/date,
    # and a string. The 'timeStamped' function is used to do this
    dump_file = open(file_name, 'w')

    # start by writing the actual stack Traceback error
    dump_file.write(str(traceback.format_exc()))

    # Write a line of dashes to seporate the stack Traceback from the
    # other variables
    dump_file.write('------' + chr(10))

    # For each variable in memory
    for variable in variables:
        # Write the variable, and valure to a file in the following format:
        # Variable_Name : Value
        dump_file.write(variable + " : " + str(variables[variable]) + chr(10))

    # Close the file
    dump_file.close()

    if show_output is True:
        return_value.append('An Internal Error Has Occured!')
        return_value.append(
            "Dump File \'{}\' Has Been Created, Containing {} Variables".format(file_name, len(variables)))


def terminate(*args):
    """
    Terminates The Script Immediately

    Usage:
        terminate
    """
    quit()


def format_command(command):
    items = variables.keys()
    items.sort(key=len)
    items.reverse()

    for item in items:
        command = command.replace(item, str(variables[item]))
    return command


def array_to_table(array, delimiter="\n", tab="\t"):
    s = [[str(e) for e in row] for row in array]
    lens = [max(map(len, col)) for col in zip(*s)]
    fmt = tab.join('{{:{}}}'.format(x) for x in lens)
    table = [fmt.format(*row) for row in s]
    return delimiter.join(table)


def get_prompt():
    if SQL is True:
        return "sql {}>".format(selected_database)
    return "{}$".format(get_cwd())


def execute_sql(command, database):
    global SQL
    global selected_database
    if type(command) is list or type(command) is tuple:
        no_table = str(command[-1]) == "\\G" or str(command[-1]) == "\\g"
        if no_table:
            command = command[:-1]
        query = ' '.join(command)
    else:
        no_table = command.lower().endswith("\\g")
        if no_table:
            command = command.replace("\\g", "").replace("\\G", "")
        query = command
    try:
        if query.lower() == "exit":
            SQL = False
            selected_database = None
            return

        if query.lower().startswith("using"):
            new_table = query[query.find(" ") + 1:]
            selected_database = new_table
            return

        elif query in config["sql_commands"]:
            query = config["sql_commands"][query]
        else:
            for cmd in config["sql_commands"]:
                if "{}" in cmd:
                    cmd_list = cmd.split(" ")
                    query_lst = query.split(" ")
                    if query_lst[0] == cmd_list[0]:
                        params = " ".join(query_lst[1:])
                        query = config["sql_commands"][cmd].format(params)
        result = variables[database].execute_update(query)
        try:
            headers = list(variables[database].description)
        except TypeError:
            return_value.append(query)
            return

        if no_table:
            spaces = 0
            for h in headers:
                if len(h[0]) > spaces:
                    spaces = len(h[0])
            spaces += 3
            for i in result:
                line = ""
                index = 0
                for item in i:
                    header = headers[index][0]
                    line += "{}:{}{}\n".format(header, " " * (spaces - len(header)), item)
                    index += 1
                return_value.append(line[:-1])
        else:
            blanks = []

            for item in range(len(headers)):
                headers[item] = headers[item][0]
                blanks.append("-" * 10)

            number_of_results = len(result)

            "PRETTY PRINT TABLE FORMAT"
            result = [headers] + [blanks] + result
            result = query + "\n\n" + array_to_table(result)

            if result == "":
                result = "No Result"
            else:
                s = "s"
                if number_of_results == 1:
                    s = ""
                result += "\n\n" + "-" * 10 + "\n{} Result{}".format(number_of_results, s)

            return_value.append(result)
    except sqlite3.OperationalError as e:
        return_value.append(query)
        return_value.append(str(e))
# endregion


# region File IO
def mkdir(*args):
    """
    Creates Directory(ies) if they do not exist.

    Usage:
        mkdir [OPTION]... DIRECTORY...

    Options:
        -v, --verbose
            Display A Message For Each Directory Created
    """
    command, args = get_command_args(args)
    for i in command:
        try:
            os.mkdir(cwd + "/" + i)
            if "v" in args or "verbose" in args:
                return_value.append("Sucsessfuly Created Directory '{}'".format(i))
        except OSError:
            return_value.append("Could Not Create Directory '{}'. It Already Exists".format(i))


def ls(*args):
    """
    Lists Contents Of A Directory

    Usage:
        ls [OPTION]... [FILE]...

    Options:
        -a, --all
            Do not ignore entries starting with .
    """
    command, args = get_command_args(args)
    files = os.listdir(cwd)
    accepted = []

    mode = 0
    if "a" in args or "all" in args:
        mode = 1
        accepted.append(".")
        accepted.append("..")

    for i in files:
        if mode == 0:
            if not i.startswith("."):
                accepted.append(i)
        else:
            accepted.append(i)

    return_value.append(config["list_delimiter"].join(accepted))


def touch(*args):
    """
    Creates A File If It Does Not Exist

    Usage:
        touch [FILE]...
    """
    command, args = get_command_args(args)
    for name in command:
        if name.startswith("-"):
            continue
        tmp = open(cwd + "/" + name, 'w')
        tmp.close()


def rmdir(*args):
    """
    Remove Directories

    Usage:
        rmdir [OPTION]... DIRECTORY...

    Options:
        -r, --recursive
            delete if not empty
    """
    command, args = get_command_args(args)
    for name in command:
        if "r" in args or "recursive" in args:
            shutil.rmtree(cwd + "/" + name)
        else:
            try:
                os.rmdir(cwd + "/" + name)
            except OSError:
                if os.path.isfile(cwd + "/" + name):
                    return_value.append("Failed To Remove '{}' Because It Is A File".format(name))
                elif os.path.isdir(cwd + "/" + name):
                    return_value.append("Failed To Remove '{}' Because It Is Not Empty".format(name))
                else:
                    return_value.append("Failed To Remove '{}' Because It Does Not Exist".format(name))


def rm(*args):
    """
    Remove Files

    Usage:
        rm FILE...
    """
    command, args = get_command_args(args)
    for name in command:
        if name.startswith("-"):
            continue
        try:
            os.remove(cwd + "/" + name)
        except OSError:
            if os.path.isdir(cwd + "/" + name):
                return_value.append("Failed To Remove '{}' Because It Is A Directory".format(name))
            else:
                return_value.append("Failed To Remove '{}' Because It Does Not Exist".format(name))


def cat(*args):
    """
    Displays Contents Of Files

    Usage:
        cat [FILE]...  
    """
    command, args = get_command_args(args)
    try:
        tmp = open(cwd + "/" + command[0], 'r')
        contents = ''.join(tmp.readlines())
        return_value.append(contents)
        tmp.close()
    except IOError:
        try:
            tmp = open(command[0], 'r')
            contents = ''.join(tmp.readlines())
            return_value.append(contents)
            tmp.close()
        except IOError:
            return_value.append("Failed To Read '{}' Because It Does Not Exist".format(command[0]))


def cp(*args):
    """
    Copies Files And Directories

    Usage:
        cp SOURCE... DIRECTORY  
    """
    command, args = get_command_args(args)

    for i in command[:-1]:
        src = cwd + "/" + i
        dst = cwd + "/" + command[-1]
        try:
            shutil.copy(src, dst)
        except IOError:
            return_value.append("Failed To Copy '{}' Because It Does Not Exist".format(i))


def mv(*args):
    """
    Moves Files And Directories

    Usage:
        mv SOURCE DIRECTORY  
    """
    command, args = get_command_args(args)

    for i in command[:-1]:
        src = cwd + "/" + i
        dst = cwd + "/" + command[-1]
        try:
            shutil.move(src, dst)
        except IOError:
            return_value.append("Failed To Copy '{}' Because It Does Not Exist".format(i))
        except shutil.Error:
            if os.path.isfile(dst + "/" + i) or os.path.isdir(dst + "/" + i):
                return_value.append("Failed To Copy '{}' Because It Already Exists In The Destination".format(i))


def tedit(*args):
    """
    Opens The File In The Text Editor

    Usage:
        tedit FILE
    """
    command, args = get_command_args(args)
    filepath = cwd + "/" + command[0]
    try:
        tmp = open(filepath, 'r')
    except IOError:
        tmp = open(filepath, 'w')
    tmp.close()

    programName = config["text_edit_program_name"]
    try:
        subprocess.Popen([programName, filepath])
    except OSError:
        return_value.append("Missing System Program '{}'".format(programName))


def to_zip(*args):
    """
    Compresses The Files And Directories To .zip Format

    Usage:
        zip FILE...
    """
    command, args = get_command_args(args)
    filename = command[0]
    if "." in filename:
        filename = filename[:filename.index(".")]
    zip_file = zipfile.ZipFile(cwd + "/" + filename + ".zip", 'w', zipfile.ZIP_DEFLATED)
    for arg in command:
        path = cwd + "/" + arg
        if os.path.isfile(path):
            zip_file.write(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    zip_file.write(os.path.join(root, file))
    zip_file.close()


def unzip(*args):
    """
    Decompresses The Files And Directories From .zip Format

    Usage:
        unzip FILE...
    """
    command, args = get_command_args(args)
    for arg in command:
        try:
            zip_file = zipfile.ZipFile(cwd + "/" + arg, 'r')
            zip_file.extractall(cwd)
            zip_file.close()
        except IOError:
            return_value.append("Could Not Extract '{}' Because It Does Not Exist".format(arg))


def trunc(*args):
    """
    Clears Contents Of Directory

    Usage:
        trunc DIRECTORY...
    """

    command, args = get_command_args(args)
    for arg in command:
        folder = cwd + "/" + arg
        try:
            shutil.rmtree(folder)
            os.mkdir(folder)
        except OSError:
            return_value.append("Could Not Truncate Directory '{}' Because It Does Not Exist".format(arg))


def wc(*args):
    """
    Counts The Number Of Words In A Directory

    Usage:
        wc [OPTION] FILE...

    Options:
        -w, --words
            Count Words

        -c, --bytes
            Count Bytes

        -m, --chars
            Count Characters

        -l, --lines
            Count Lines

        --max-line-length
            Returns The Length Of The Longest Line
    """

    mode_replacements = {
        "words": "w",
        "bytes": "c",
        "chars": "m",
        "lines": "l",
        "max-line-length": "L"
    }
    try:
        space = len(max(args, key=len)) + 3
    except ValueError:
        return
    mode = "w"

    command, args = get_command_args(args)
    if len(args) == 0:
        args = ["w"]

    if args[0].startswith("-"):
        mode = args[0].replace("-", "")
        if mode in mode_replacements:
            mode = mode_replacements[mode]

    for arg in command:
        count = 0
        filename = cwd + "/" + arg

        try:
            with open(filename, 'r') as file:

                if mode == "w":
                    for line in file:
                        count += len(line.split())

                elif mode == "c":
                    count = os.stat(filename).st_size

                elif mode == "m":
                    count = len(file.read())

                elif mode == "l":
                    for i, l in enumerate(file):
                        pass
                    count = i + 1

                elif mode == "L":
                    count = len(max(file, key=len))
        except IOError:
            return_value.insert(0,
                                "Could Not Check File '{}' Because It Either Does Not Exist Or Is A Directory".format(
                                    arg))
            continue
        return_value.append(arg + " " * (space - len(arg)) + str(count))


def du(*args):
    """
    Returns The Amount Of Space Which Is Taken Up By A Directory

    Usage:
        du DIRECTORY...
    """

    command, args = get_command_args(args)

    try:
        space = len(max(command, key=len)) + 3
    except ValueError:
        return

    for arg in command:
        path = cwd + "/" + arg
        total_size = 0
        seen = set()
        if not os.path.isdir(path):
            return_value.insert(0,
                                "Could Not Check Directory '{}' Because It Either Does Not Exist Or Is A File".format(
                                    arg))
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)

                try:
                    stat = os.stat(fp)
                except OSError:
                    continue

                if stat.st_ino in seen:
                    continue

                seen.add(stat.st_ino)

                total_size += stat.st_size
        return_value.append(arg + " " * (space - len(arg)) + str(total_size))
# endregion


# region Navigation
def cd(*args):
    """
    Changes The Current Working Directory

    Usage:
        cd DIRECTORY
    """
    command, args = get_command_args(args)

    global cwd
    if command[0] == "..":
        new = "/".join(cwd.split("/")[:-1])
        if new.startswith(directory_path):
            cwd = new
    elif command[0] == "~":
        cwd = config["directory_root"] + config["start_location"]
    elif command[0] == "/":
        cwd = config["directory_root"]
    elif command[0].startswith(config["directory_root"]):
        if os.path.isdir(command[0]):
            cwd = command[0]
        else:
            return_value.append(
                "Could Not Navigate To {} Because The Directory Either Does Not Exist Or Is A File".format(command[0]))
    else:
        dst = cwd
        dst.replace("\\", "/")
        dst = dst.split("/")

        for i in range(command[0].count("../")):
            try:
                del dst[-1]
            except IndexError:
                break
        dst = "/".join(dst)
        command[0] = command[0].replace("../", "")
        if dst == "":
            cwd = config["directory_root"]
        if os.path.isdir(cwd + "/" + command[0]):
            cwd += "/" + command[0]
        elif os.path.isdir(dst + "/" + command[0]):
            cwd = dst + "/" + command[0]
        else:
            return_value.append(
                "Could Not Navigate To {} Because The Directory Either Does Not Exist Or Is A File".format(command[0]))


def pwd(*args):
    """
    Prints Name Of Working Directory

    Usage:
        pwd
    """
    command, args = get_command_args(args)
    return_value.append(cwd)


def setpwd(*args):
    """
    Sets The Working Directory

    Usage:
        setpwd DIRECTORY
    """
    command, args = get_command_args(args)

    global cwd
    new = command[0]
    if os.path.isdir(new):
        if new.startswith(directory_path):
            cwd = new
        else:
            return_value.append(
                "Could Not Set The Working Directory To '{}' Because The Directory Is Not Under The Acceptable File Structure".format(
                    command[0]))
    else:
        return_value.append(
            "Could Not Set The Working Directory To '{}' Because The Directory Does Not Exist".format(command[0]))


def cdls(*args):
    """
    Changes The Current Working Directory And Displays The Contents Of The New Directory

    Usage:
        cd DIRECTORY [OPTION]...

    Options:
        -a, --all
            Do not ignore entries starting with .
    """
    cd(*args)
    ls(*args)


def sdir(*args):
    """
    Changes The Current Working Directory To The Default Start Directory

    Usage:
        sdir
    """
    command, args = get_command_args(args)
    global cwd
    cwd = directory_path + config["start_location"]

# endregion


# region System
def shutdown(*args):
    """
    Shuts Down The System

    Usage:
        shutdown [DELAY]
    """

    command, args = get_command_args(args)

    time_replacement = {
        "now": 0
    }

    if len(command) > 0:
        delay = command[0]
    else:
        delay = 0
    if delay in time_replacement:
        delay = time_replacement[delay]
    else:
        try:
            delay = int(delay)
        except ValueError:
            return_value.append("'{}' Is An Invalid Shutdown Delay. Shutdown Has Been Aborted".format(delay))
            return

    time.sleep(delay)

    terminate()


def history(*args):
    """
    Displays Command History

    Usage:
        history [COMMANDS]
    """
    command, args = get_command_args(args)
    try:
        show = int(command[0])
    except IndexError:
        show = config["default_history_commands"]
    except ValueError:
        return_value.append("'{}' Is An Invalid Number Of Commands To Show".format(command[0]))
        return
    return_value.append("\n".join(command_history[-show:]))


def clearhistory(*args):
    """
    Clears Command History

    Usage:
        clearhistory
    """
    command, args = get_command_args(args)
    global command_history
    command_history = []


def date(*args):
    """
    Displays The System Date And Time

    Usage:
        date
    """
    command, args = get_command_args(args)
    return_value.append(datetime.datetime.today().strftime(config["date_format"]))


def sysinfo(*args):
    """
    Displays System Information

    Usage:
        sysinfo
    """
    command, args = get_command_args(args)

    values = {
        "OS": platform.system(),
        "Release": platform.release(),
        "Version": platform.version(),
        "Machine": platform.machine(),
        "Platform": platform.platform(),
    }
    space = len(max(values.keys(), key=len)) + 3

    for key, val in values.items():
        return_value.append(key + " " * (space - len(key)) + str(val))


def whoami(*args):
    """
    Displays Name Of User

    Usage:
        whoami
    """
    command, args = get_command_args(args)
    return_value.append(getpass.getuser())


def startup(*args):
    """
    Runs The System's Startup Scripts

    Usage:
        startup
    """
    command, args = get_command_args(args)

    script = config["startup_script"]

    default_structure = config["default_structure"]

    if not os.path.isdir(directory_path):
        for dir in default_structure:
            os.makedirs(directory_path + dir)

    for line in script:
        output = interpret_command(line)
        if output != []:
            print('\n'.join(output))


def math(*args):
    """
    Calculates Mathimatical Operation

    Usage:
        math OPERATION
    """

    # list of safe methods
    safe_list = ['acos', 'asin', 'atan', 'atan2', 'ceil', 'cos',
                 'cosh', 'degrees', 'e', 'exp', 'fabs', 'floor',
                 'fmod', 'frexp', 'hypot', 'ldexp', 'log', 'log10',
                 'modf', 'pi', 'pow', 'radians', 'sin', 'sinh', 'sqrt',
                 'tan', 'tanh']

    # creating a dictionary of safe methods
    safe_dict = dict([(k, locals().get(k, None)) for k in safe_list])

    command, args = get_command_args(args)

    try:
        return_value.append(str(eval(format_command("".join(command)), safe_dict)))
    except SyntaxError:
        if "".join(command) == "":
            raise IndexError
        return_value.append("'{}' Is An Invalid Mathematical Operation".format("".join(command)))
    except (ZeroDivisionError, ValueError):
        return_value.append("'{}' Is An Impossible Mathematical Operation".format("".join(command)))
    except NameError:
        return_value.append("Mathematical Operation '{}' Contains Undefined Values".format("".join(command)))


def set(*args):
    """
    Defines A New Variable

    Usage:
        set KEY VALUE
    """
    command, args = get_command_args(args)
    variables[command[0]] = command[1]


def error(*args):
    """
    Displays The Most Recent Error

    Usage:
        error
    """
    command, args = get_command_args(args)
    path = str(config["directory_root"] + config["error_report_directory"])
    dates = {}

    if os.listdir(path) == []:
        return_value.append("There Are No Logged Errors To Display")
        return

    stamp_format = config["dump_file_format"]
    while "{" in stamp_format:
        start = stamp_format.index("{")
        end = stamp_format.index("}")
        stamp_format = stamp_format[:start] + stamp_format[end + 1:]

    for dump_file in os.listdir(path):
        convert = dump_file.replace(config["error_report_filename"], "")
        dates[time.mktime(datetime.datetime.strptime(convert, stamp_format).timetuple())] = dump_file

    file_date = max(dates.keys())
    filename = dates[file_date]

    cat(config["directory_root"] + config["error_report_directory"] + "/" + filename)


def vars(*args):
    """
    Displays All Of The System Variables

    Usage:
        vars
    """
    space = max(len(x) for x in variables) + 3
    for key, value in variables.items():
        return_value.append("{}{}{}".format(key, " " * (space - len(key)), value))


def unixdate(*args):
    """
    Converts unix time to datetime

    Usage:
        unixdate UNIXTIME [FORMAT]
    """
    timestamp = int(float(args[0]))
    style = '%Y-%m-%d %H:%M:%S'
    if len(args) > 1:
        style = ' '.join(args[1:])

    return_value.append(datetime.datetime.utcfromtimestamp(timestamp).strftime(style))


def unixtime(*args):
    """
    Returns Unix Time

    Usage:
        unixtime
    """
    return_value.append(str(time.time()))
# endregion


# region Console
def echo(*args):
    """
    Displays A Line Of Text

    Usage:
        echo [TEXT]...
    """
    command, args = get_command_args(args)

    # if ">" in command:
    #     # overwrite
    #     try:
    #         filename = ' '.join(command[command.index(">") + 1:])
    #         tmp = open(cwd + "/" + filename, 'w')
    #         tmp.write(' '.join(command[:command.index(">")]) + "\n")
    #         tmp.close()
    #     except IOError:
    #         return_value.append("Please Specify A Filename To Write To")
    #
    # elif ">>" in command:
    #     # append
    #
    #     try:
    #         filename = ' '.join(command[command.index(">>") + 1:])
    #         tmp = open(cwd + "/" + filename, 'a')
    #         tmp.write(' '.join(command[:command.index(">>")]) + "\n")
    #         tmp.close()
    #     except IOError:
    #         return_value.append("Please Specify A Filename To Append To")
    # else:
    return_value.append(" ".join(command))


def clear(*args):
    """
    Clears The Console Screen

    Usage:
        clear
    """
    command, args = get_command_args(args)
    os.system('cls' if os.name == 'nt' else 'clear')


def sleep(*args):
    """
    Pauses The Terminal For A Specified Amount Of Time

    Usage:
        sleep [DELAY]
    """
    command, args = get_command_args(args)
    try:
        time.sleep(int(command[0]))
    except ValueError:
        return_value.append("'{}' Is An Invalid Time Delay. Delay Has Been Aborted".format(command[0]))
        return


def system(*args):
    """
    Executes A System Command

    Usage:
        system COMMAND
    """
    command, args = get_command_args(args)
    os.system(" ".join(command))


# endregion


# region Network
def ping(*args):
    """
    Send ICMP ECHO_REQUEST To Specified Host

    Usage:
        ping HOST
    """
    command, args = get_command_args(args)

    os.system("ping {}".format(' '.join(command)))


def wget(*args):
    """
    Make Web Request And Save Result

    Usage:
        wget URL FILENAME
    """

    command, args = get_command_args(args)
    url = command[0]
    try:

        try:
            r = requests.get(url, allow_redirects=True)
            open(cwd + "/" + command[1], 'wb').write(r.content)
        except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
            try:
                r = requests.get("http://" + url, allow_redirects=True)
                open(cwd + "/" + command[1], 'wb').write(r.content)
            except requests.exceptions.MissingSchema:
                return_value.append("'{}' Is Invalid As It Is Missing The Schema".format(url))

    except requests.exceptions.ConnectionError:
        return_value.append("Could Not Connect To Server '{}'".format(url))


def curl(*args):
    """
    Make Web Request And Display Result To Console

    Usage:
        curl URL
    """

    command, args = get_command_args(args)
    url = command[0]
    try:

        try:
            r = requests.get(url, allow_redirects=True)
            return_value.append(r.content)

        except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
            try:
                r = requests.get("http://" + url, allow_redirects=True)
                return_value.append(r.content)

            except requests.exceptions.MissingSchema:
                return_value.append("'{}' Is Invalid As It Is Missing The Schema".format(url))

    except requests.exceptions.ConnectionError:
        return_value.append("Could Not Connect To Server '{}'".format(url))


def ipconfig(*args):
    """
    Displays Network Configurations To The Console

    Usage:
        ipconfig
    """

    command, args = get_command_args(args)

    proc = subprocess.check_output("ipconfig").decode('utf-8')
    return_value.append(proc)


# endregion


# region Executable
def execute_file(path):
    global return_value

    old_cwd = os.getcwd()
    dir, name = os.path.split(path)
    os.chdir(dir)
    if path.endswith(".py"):
        python_code = "".join(open(name, 'r').readlines())
        exec(python_code)
    elif path.endswith(".jar"):
        process = subprocess.Popen(['java', '-jar', path])
        process.wait()
    elif path.endswith(".exe"):
        process = subprocess.Popen([path])
        process.wait()
    else:
        val = []
        shell_code = open(path, 'r').readlines()
        for line in shell_code:
            try:
                interpret_command(line.replace("\n", ""))
                val += return_value
            except TypeError:
                val.append("Could Not Read File")
        return_value = val
    os.chdir(old_cwd)


def python(*args):
    """
    Executes Script As Python

    Usage:
        python [ARGS]...

    try 'python -h' for more details 
    """
    args = list(args)
    for i in range(len(args)):
        if os.path.isfile(cwd + "/" + args[i]):
            args[i] = cwd + "/" + args[i]

    if config["capture_program_output"]:
        proc = subprocess.check_output("python " + " ".join(args)).decode('utf-8')
        return_value.append(proc)
    else:
        os.system("python " + " ".join(args))


def java(*args):
    """
    Executes Script As Java

    Usage:
        java [ARGS]...

    try 'java -?' for more details 
    """
    args = list(args)
    for i in range(len(args)):
        if os.path.isfile(cwd + "/" + args[i]):
            args[i] = cwd + "/" + args[i]

    if config["capture_program_output"]:
        proc = subprocess.check_output("java -jar " + " ".join(args)).decode('utf-8')
        return_value.append(proc)
    else:
        os.system("java -jar " + " ".join(args))


# endregion


# region SQL
def sql(*args):
    """
    Connect to, or query an SQL database

    Usage:
        sql CONNECT DATABASE AS NAME                            - Connects To Database
        sql NAME QUERY...                                       - Executes Query In Specified Database
        sql NAME                                                - Opens SQL Prompt In The Specified Database
    """
    global SQL
    global selected_database
    if args[0].lower() == "connect":
        if "as" not in args:
            return_value.append("Please Specify A Name To Save This Connection As, Using The 'as' Keyword")
            return
        name_index = args.index("as")
        name = args[name_index + 1]
        connection_info = args[1: name_index]
        if len(connection_info) == 1:
            if os.path.isfile(connection_info[0]):
                connection = SQLConnection(connection_info[0])
                variables[name] = connection
                return_value.append("Sucsessfuly Connected To Database '{}'".format(connection_info[0]))
            elif os.path.isfile(cwd + "/" + connection_info[0]):
                connection = SQLConnection(cwd + "/" + connection_info[0])
                variables[name] = connection
                return_value.append("Sucsessfuly Connected To Database '{}'".format(connection_info[0]))
            else:
                return_value.append("Could Not Connect To Database '{}'".format(connection_info[0]))
        # else:
        #     host = connection_info[0]
        #     username = connection_info[1]
        #     password = connection_info[2]
        #     connection = SQLConnection(host, username, password)

    elif args[0] in variables:
        if len(args) == 1:
            SQL = True
            selected_database = args[0]
            return
        execute_sql(args[1:], args[0])
# endregion


# region Help
def help(*args):
    """
    Displays The Entire Command Reference

    Usage:
        help
    """
    command, args = get_command_args(args)

    current_module = sys.modules[__name__]
    delete = ['array_to_table', 'SQLConnection', 'format_command', 'terminate', 'traceback', 'dump', '__builtins__',
              '__doc__', '__file__', '__name__', '__package__', 'command_to_function', 'cwd', 'datetime',
              'directory_path', 'execute_file', 'get_command_args', 'get_cwd', 'get_docstring', 'command_history',
              'platform', 'interpret_command', 'os', 'return_value', 'shutil', 'subprocess', 'sys', 'temporary_storage',
              'time', 'variables', 'zipfile', 'getpass', 'requests', 'config', 're', "sqlite3", "SQL", "execute_sql",
              "selected_database", "get_prompt", "overridden", "mysql", "item", "i", "__cached__ ", "__loader__",
              "__spec__", "__warningregistry__"
              ]
    delete += config["disabled_commands"]
    modules = dir(current_module)
    approved = []

    return_value.append("Commands: ")
    for mod in modules:
        if mod not in delete:
            approved.append(mod)

    tab = 2
    space = 2

    total_pad = len(max(approved, key=len)) + space
    for mod in approved:
        pad = total_pad - len(mod)
        text = get_docstring(mod)
        text = text.split("\n")
        if text[0].replace(" ", "").replace("\t", "") == "":
            del text[0]
        for i in range(len(text)):
            if i == 0:
                text[i] = text[i].replace("    ", "", 1)
            else:
                text[i] = text[i].replace("    ", " " * (total_pad + tab), 1)
        text = "\n".join(text)

        return_value.append(" " * tab + mod + " " * pad + text)

# endregion


# region Override Initialization
overridden = config["overrides"]

if type(overridden) is str:
    overridden = [overridden]

for item in overridden:
    for i in config["overrides"]:
        try:
            exec(''.join(open(i, 'r').readlines()))
        except IOError:
            print("Could Not Open Configuration File '{}'".format(i))
# endregion

startup()
