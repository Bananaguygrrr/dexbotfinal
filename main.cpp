#include <cstdlib>
#include <iostream>
#include <string>

#ifndef _WIN32
#include <sys/wait.h>
#endif

namespace {

void mark_booted_by_cpp() {
#ifdef _WIN32
    _putenv_s("DEXBOT_BOOTED_BY_CPP", "1");
#else
    setenv("DEXBOT_BOOTED_BY_CPP", "1", 1);
#endif
}

std::string default_python_command() {
#ifdef _WIN32
    return "python bot.py";
#else
    return "python3 bot.py";
#endif
}

int normalize_exit_code(int system_result) {
    if (system_result == -1) {
        return 127;
    }

#ifdef _WIN32
    return system_result;
#else
    if (WIFEXITED(system_result)) {
        return WEXITSTATUS(system_result);
    }
    if (WIFSIGNALED(system_result)) {
        return 128 + WTERMSIG(system_result);
    }
    return system_result;
#endif
}

}  // namespace

int main() {
    mark_booted_by_cpp();

    const char* configured_command = std::getenv("DEXBOT_PYTHON_COMMAND");
    std::string command =
        configured_command != nullptr && configured_command[0] != '\0'
            ? configured_command
            : default_python_command();

    std::cout << "dexbot C++ boot wrapper starting: " << command << std::endl;
    int result = std::system(command.c_str());
    int exit_code = normalize_exit_code(result);
    std::cout << "dexbot C++ boot wrapper stopped with exit code " << exit_code << std::endl;
    return exit_code;
}
