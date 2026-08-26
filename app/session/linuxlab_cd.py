import os
import sys

from app.session.current_directory import (
    set_current_directory
)


def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python -m app.session.linuxlab_cd <directory>"
        )

        sys.exit(1)

    directory = os.path.abspath(
        os.path.expanduser(
            sys.argv[1]
        )
    )

    if not os.path.isdir(directory):

        print(
            f"Directory does not exist: {directory}"
        )

        sys.exit(1)

    set_current_directory(
        directory
    )

    print(
        f"Visual Lab location: {directory}"
    )


if __name__ == "__main__":
    main()
