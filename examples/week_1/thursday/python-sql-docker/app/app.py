import json
import logging
from http.server import SimpleHTTPRequestHandler, HTTPServer
from app.dao import SystemLogDAO
from app.exceptions import DatabaseConnectionError, LogCreationError

# Initialize global Data Access Object instance
dao = SystemLogDAO()

class logApiHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        """Fetches records out of database and responds with JSON strings"""
        if self.path == "/logs":
            logs = dao.get_all_logs()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            # JSON Serialization
            self.wfile.write(json.dumps(logs, indent=2).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint Not Found")
    
    def do_POST(self):
        """Accepts an incoming JSON payload to write a log entry."""
        if self.path == "/logs":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                # JSON Deserialization
                data = json.loads(post_data.decode('utf-8'))

                # interface with OOP DAO layer
                dao.insert_log(
                    host=data["host"],
                    severity=data["severity"],
                    message=data["message"]
                )

                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Log stored"}).encode('utf-8'))

            except (json.JSONDecodeError, KeyError) as err:
                logging.warning(f"Malformed API request payload schema: {err}")
                self.send_error(400, "Bad Request: Check schema payload properties")
            except DatabaseConnectionError:
                self.send_error(503, "Database backend inaccessible")
            except LogCreationError:
                self.send_error(500, "Pipeline error")
        else:
            self.send_error(404, "Endpoint not found")
    
def run(port=8081):
    server = HTTPServer(('0.0.0.0', port), logApiHandler)

    logging.info(f"HTTP Endpoint online and bound on port {port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logging.info("Server terminated")

if __name__ == "__main__":
    run()