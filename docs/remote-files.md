# Target files and logs

logs.read verifies JobRef identity and reads a finite stdout/stderr chunk from the native job's target output paths (or the generated allocation's target work directory). It returns text, bytes_read and next_offset.

files.read and files.write address files under the registered target_root. Read/write chunks are limited to 256 KiB; content uses base64. Local symlink escape is rejected. Remote paths use the authenticated target account's filesystem; target_root is path scoping, not an OS sandbox against a hostile account modifying symlinks.

files.transfer uses system rsync for same-target copying and local-to-SSH or SSH-to-local transfer. Two distinct SSH targets require explicit staging; molq does not infer cross-target aliases. System OpenSSH configuration and multiplexing are preserved.

Missing paths, tools or permissions return structured errors. No whole-file job artifacts or workspace database is created.
